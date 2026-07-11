"""Resolve packaged assets to paths PyBullet can load on Windows."""

import atexit
import hashlib
from importlib.resources import files
from multiprocessing.util import Finalize
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import xml.etree.ElementTree as etxml

_CACHE_DIR = None
_CACHE_PID = None
_CACHE_FINALIZER = None


def resolve_package_asset(asset, *, resource_root=None):
    """Return an ASCII path for a packaged asset or absolute source path."""
    requested = os.fspath(asset)
    if os.path.isabs(requested):
        if requested.isascii():
            return requested
        source = Path(requested)
        asset_parts = _asset_parts(source.name)
        staged_files = _collect_filesystem_asset(source.parent, asset_parts)
    else:
        asset_parts = _asset_parts(requested)
        package_root = (
            files("gym_pybullet_drones") if resource_root is None else resource_root
        )
        assets_root = package_root.joinpath("assets")
        if isinstance(assets_root, Path):
            source = assets_root.joinpath(*asset_parts)
            if str(source).isascii():
                return str(source)
            staged_files = _collect_filesystem_asset(assets_root, asset_parts)
        else:
            staged_files = _collect_traversable_asset(assets_root, asset_parts)

    return _stage_files(staged_files, asset_parts)


def _asset_parts(path):
    parts = _relative_parts(path, "asset path")
    if any(not part.isascii() for part in parts):
        raise ValueError(f"Non-ASCII asset filename is not supported: {path!r}")
    return parts


def _relative_parts(path, label):
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError(f"Unsafe {label}: {path!r}")
    normalized = path.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    first_part = normalized.split("/", 1)[0]
    if (
        posix_path.is_absolute()
        or PureWindowsPath(path).is_absolute()
        or ":" in first_part
        or any(part == ".." for part in posix_path.parts)
    ):
        raise ValueError(f"Unsafe {label}: {path!r}")
    parts = tuple(part for part in posix_path.parts if part != ".")
    if not parts:
        raise ValueError(f"Unsafe {label}: {path!r}")
    return parts


def _collect_filesystem_asset(root, asset_parts):
    root = _regular_directory(root, "asset root")
    source = _regular_file(root, asset_parts, "Asset path")
    return _collect_asset_files(
        asset_parts,
        source.read_bytes(),
        lambda parts: _regular_file(root, parts, "URDF mesh path").read_bytes(),
    )


def _collect_traversable_asset(root, asset_parts):
    if not root.is_dir():
        raise ValueError("Packaged asset root is not a directory")
    source = _traversable_file(root, asset_parts, "Asset path")
    return _collect_asset_files(
        asset_parts,
        source.read_bytes(),
        lambda parts: _traversable_file(root, parts, "URDF mesh path").read_bytes(),
    )


def _collect_asset_files(asset_parts, asset_bytes, read_dependency):
    staged_files = {asset_parts: asset_bytes}
    if asset_parts[-1].lower().endswith(".urdf"):
        try:
            root = etxml.fromstring(asset_bytes)
        except etxml.ParseError as exc:
            raise ValueError("Packaged URDF is not valid XML") from exc
        for mesh in root.iter("mesh"):
            mesh_name = mesh.attrib.get("filename")
            if not mesh_name:
                continue
            mesh_parts = _relative_parts(mesh_name, "URDF mesh path")
            if any(not part.isascii() for part in mesh_parts):
                raise ValueError(
                    f"Non-ASCII asset filename is not supported: {mesh_name!r}"
                )
            dependency_parts = asset_parts[:-1] + mesh_parts
            staged_files[dependency_parts] = read_dependency(dependency_parts)
    return staged_files


def _regular_directory(path, label):
    try:
        resolved = Path(path).resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} does not exist: {path}") from exc
    if not stat.S_ISDIR(resolved.stat().st_mode):
        raise ValueError(f"{label} is not a directory: {path}")
    return resolved


def _regular_file(root, parts, label):
    candidate = root.joinpath(*parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            f"{label} does not reference a regular file: {candidate}"
        ) from exc
    if not _is_relative_to(resolved, root):
        raise ValueError(f"{label} escapes the asset root: {candidate}")
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise ValueError(f"{label} does not reference a regular file: {candidate}")
    return resolved


def _traversable_file(root, parts, label):
    resource = root
    for part in parts:
        resource = resource.joinpath(part)
    if not resource.is_file():
        raise ValueError(f"{label} does not reference a regular file")
    return resource


def _stage_files(staged_files, asset_parts):
    cache_root = _regular_directory(_process_cache_dir(), "asset cache root")
    namespace = cache_root / _content_key(staged_files)
    _create_safe_directories(cache_root, (namespace.name,))
    namespace = namespace.resolve(strict=True)

    for parts, data in staged_files.items():
        _write_cached_file(namespace, parts, data)

    destination = namespace.joinpath(*asset_parts)
    if not str(destination).isascii():
        raise ValueError(f"Resolved PyBullet asset path is not ASCII: {destination}")
    return str(destination)


def _content_key(staged_files):
    digest = hashlib.sha256()
    for parts, data in sorted(staged_files.items()):
        name = "/".join(parts).encode("ascii")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def _write_cached_file(root, parts, data):
    parent = _create_safe_directories(root, parts[:-1])
    destination = parent / parts[-1]
    if destination.exists() or destination.is_symlink():
        _validate_cached_file(destination, data)
        return

    descriptor, temporary_name = tempfile.mkstemp(prefix=".asset-", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            _validate_cached_file(destination, data)
        except OSError:
            _atomic_replace_file(temporary, destination, data)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace_file(temporary, destination, data):
    if destination.exists() or destination.is_symlink():
        _validate_cached_file(destination, data)
        return
    try:
        os.replace(temporary, destination)
    except OSError:
        if destination.exists() or destination.is_symlink():
            _validate_cached_file(destination, data)
            return
        raise
    _validate_cached_file(destination, data)


def _create_safe_directories(root, parts):
    current = root
    for part in parts:
        child = current / part
        if child.exists() or child.is_symlink():
            if child.is_symlink() or not child.is_dir():
                raise ValueError(
                    f"Asset cache destination is not a safe directory: {child}"
                )
        else:
            child.mkdir()
        current = child.resolve(strict=True)
        if not _is_relative_to(current, root):
            raise ValueError(f"Asset cache destination escapes its root: {child}")
    return current


def _validate_cached_file(path, expected_bytes):
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"Cached asset is not a regular file: {path}")
    if path.read_bytes() != expected_bytes:
        raise ValueError(f"Cached asset content does not match its source: {path}")


def _is_relative_to(path, root):
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _process_cache_dir():
    global _CACHE_DIR, _CACHE_PID, _CACHE_FINALIZER

    process_id = os.getpid()
    if _CACHE_DIR is not None and _CACHE_PID == process_id:
        return _CACHE_DIR

    candidates = [tempfile.gettempdir()]
    if os.name == "nt":
        candidates.extend([
            os.environ.get("PUBLIC"),
            os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp"),
        ])

    for candidate in dict.fromkeys(candidates):
        if candidate is None:
            continue
        candidate = Path(candidate)
        if not candidate.is_absolute():
            candidate = candidate.resolve()
        if not str(candidate).isascii():
            continue
        try:
            candidate = _regular_directory(candidate, "cache candidate")
            cache_dir = Path(tempfile.mkdtemp(
                prefix=f"gym-pybullet-drones-{process_id}-", dir=candidate
            )).resolve(strict=True)
        except (OSError, ValueError):
            continue
        if not cache_dir.is_absolute() or not str(cache_dir).isascii():
            shutil.rmtree(cache_dir, ignore_errors=True)
            continue
        _CACHE_DIR = cache_dir
        _CACHE_PID = process_id
        atexit.register(_cleanup_cache, cache_dir, process_id)
        _CACHE_FINALIZER = Finalize(
            None, _cleanup_cache, args=(cache_dir, process_id), exitpriority=10
        )
        return cache_dir

    raise RuntimeError("Could not create a writable ASCII cache for PyBullet assets")


def _cleanup_cache(cache_dir, process_id):
    if os.getpid() == process_id:
        shutil.rmtree(cache_dir, ignore_errors=True)
