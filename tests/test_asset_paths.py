import errno
import multiprocessing
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

import pybullet as p
import pytest


def _load_urdf(path):
    client = p.connect(p.DIRECT)
    try:
        return p.loadURDF(str(path), physicsClientId=client)
    finally:
        p.disconnect(client)


def _package_assets():
    return Path(__file__).parents[1] / "gym_pybullet_drones" / "assets"


def _write_urdf(assets_dir, mesh_name, asset_name="cf2x.urdf"):
    urdf = (_package_assets() / "cf2x.urdf").read_text(encoding="utf-8")
    path = assets_dir / asset_name
    path.write_text(urdf.replace("./cf2.dae", mesh_name), encoding="utf-8")
    return path


def _load_packaged_urdf_in_child(result_queue, asset_path):
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    resolved = resolve_package_asset(asset_path)
    body = _load_urdf(resolved)
    result_queue.put((os.getpid(), resolved, body))


def test_ascii_asset_path_is_returned_unchanged():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    source = (
        "C:/ascii-assets/cf2x.urdf"
        if os.name == "nt"
        else "/ascii-assets/cf2x.urdf"
    )

    assert resolve_package_asset(source) == source


def test_unicode_urdf_is_staged_with_its_relative_mesh():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    package_assets = _package_assets()
    with tempfile.TemporaryDirectory(prefix="gpd-assets-test-") as temp_dir:
        unicode_assets = Path(temp_dir) / "\u8d44\u4ea7"
        unicode_assets.mkdir()
        shutil.copy2(package_assets / "cf2x.urdf", unicode_assets / "cf2x.urdf")
        shutil.copy2(package_assets / "cf2.dae", unicode_assets / "cf2.dae")

        resolved = Path(resolve_package_asset(unicode_assets / "cf2x.urdf"))

        assert str(resolved).isascii()
        assert resolved != unicode_assets / "cf2x.urdf"
        assert (resolved.parent / "cf2.dae").is_file()
        assert _load_urdf(resolved) >= 0


def test_packaged_urdf_loads_through_resolver():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    resolved = Path(resolve_package_asset("cf2x.urdf"))

    assert str(resolved).isascii()
    assert (resolved.parent / "cf2.dae").is_file()
    assert _load_urdf(resolved) >= 0


def test_ctrl_aviary_loads_packaged_drone_urdf():
    from gym_pybullet_drones.envs.CtrlAviary import CtrlAviary

    environment = None
    try:
        environment = CtrlAviary(gui=False)

        assert p.getBodyInfo(
            int(environment.DRONE_IDS[0]), physicsClientId=environment.CLIENT
        )
    finally:
        if environment is not None:
            environment.close()
        elif p.isConnected():
            p.disconnect()


def test_zip_traversable_asset_is_staged_and_loadable():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-zip-assets-test-") as temp_dir:
        archive_path = Path(temp_dir) / "assets.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(
                _package_assets() / "cf2x.urdf", "package/assets/cf2x.urdf"
            )
            archive.write(_package_assets() / "cf2.dae", "package/assets/cf2.dae")

        with zipfile.ZipFile(archive_path) as archive:
            resource_root = zipfile.Path(archive, at="package/")
            resolved = Path(
                resolve_package_asset("cf2x.urdf", resource_root=resource_root)
            )

            assert str(resolved).isascii()
            assert (resolved.parent / "cf2.dae").is_file()
            assert _load_urdf(resolved) >= 0


@pytest.mark.parametrize(
    "mesh_name",
    ["../outside.dae", "/outside.dae", "C:/outside.dae", "package://outside.dae"],
)
def test_unsafe_urdf_mesh_paths_are_rejected(mesh_name):
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-unsafe-mesh-test-") as temp_dir:
        temp_root = Path(temp_dir)
        assets_dir = temp_root / "\u8d44\u4ea7"
        assets_dir.mkdir()
        shutil.copy2(_package_assets() / "cf2.dae", temp_root / "outside.dae")
        urdf_path = _write_urdf(assets_dir, mesh_name)

        with pytest.raises(ValueError, match="Unsafe URDF mesh path"):
            resolve_package_asset(urdf_path)


def test_mesh_symlink_escape_is_rejected():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-mesh-symlink-test-") as temp_dir:
        temp_root = Path(temp_dir)
        assets_dir = temp_root / "\u8d44\u4ea7"
        assets_dir.mkdir()
        outside_mesh = temp_root / "outside.dae"
        shutil.copy2(_package_assets() / "cf2.dae", outside_mesh)
        try:
            os.symlink(outside_mesh, assets_dir / "linked.dae")
        except OSError as exc:
            if (
                exc.errno in {errno.EACCES, errno.EPERM}
                or getattr(exc, "winerror", None) == 1314
            ):
                pytest.skip("symlink creation is not permitted on this system")
            raise
        urdf_path = _write_urdf(assets_dir, "linked.dae")

        with pytest.raises(ValueError, match="escapes the asset root"):
            resolve_package_asset(urdf_path)


def test_non_regular_mesh_is_rejected():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-mesh-file-test-") as temp_dir:
        assets_dir = Path(temp_dir) / "\u8d44\u4ea7"
        assets_dir.mkdir()
        (assets_dir / "mesh.dae").mkdir()
        urdf_path = _write_urdf(assets_dir, "mesh.dae")

        with pytest.raises(ValueError, match="regular file"):
            resolve_package_asset(urdf_path)


def test_non_ascii_asset_filename_is_rejected():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-filename-test-") as temp_dir:
        assets_dir = Path(temp_dir) / "\u8d44\u4ea7"
        assets_dir.mkdir()
        shutil.copy2(_package_assets() / "cf2.dae", assets_dir / "cf2.dae")
        urdf_path = _write_urdf(assets_dir, "./cf2.dae", "\u65e0\u4eba\u673a.urdf")

        with pytest.raises(ValueError, match="Non-ASCII asset filename"):
            resolve_package_asset(urdf_path)


def test_staged_asset_is_not_rewritten_when_it_already_exists():
    from gym_pybullet_drones.utils.assets import resolve_package_asset

    with tempfile.TemporaryDirectory(prefix="gpd-idempotent-test-") as temp_dir:
        assets_dir = Path(temp_dir) / "\u8d44\u4ea7"
        assets_dir.mkdir()
        shutil.copy2(_package_assets() / "cf2.dae", assets_dir / "cf2.dae")
        urdf_path = _write_urdf(assets_dir, "./cf2.dae")
        resolved = Path(resolve_package_asset(urdf_path))
        os.utime(resolved, ns=(1_000_000_000_000_000_000,) * 2)
        marked_mtime = resolved.stat().st_mtime_ns

        second_resolution = resolve_package_asset(urdf_path)

        assert second_resolution == str(resolved)
        assert resolved.stat().st_mtime_ns == marked_mtime


def test_atomic_fallback_handles_hardlink_failure_and_concurrent_writer(
    monkeypatch,
):
    from gym_pybullet_drones.utils import assets as asset_module

    link_calls = []
    replace_calls = []

    def reject_hardlink(source, destination):
        link_calls.append((source, destination))
        raise OSError(errno.EPERM, "hard links are unavailable")

    def concurrent_replace(source, destination):
        replace_calls.append((source, destination))
        shutil.copyfile(source, destination)
        raise FileExistsError(errno.EEXIST, "destination was created concurrently")

    monkeypatch.setattr(asset_module.os, "link", reject_hardlink)
    monkeypatch.setattr(asset_module.os, "replace", concurrent_replace)

    with tempfile.TemporaryDirectory(prefix="gpd-link-fallback-test-") as temp_dir:
        assets_dir = Path(temp_dir) / "\u8d44\u4ea7"
        assets_dir.mkdir()
        shutil.copy2(_package_assets() / "cf2.dae", assets_dir / "cf2.dae")
        urdf_path = _write_urdf(assets_dir, "./cf2.dae")
        urdf_path.write_text(
            urdf_path.read_text(encoding="utf-8") + "\n<!-- fallback -->\n",
            encoding="utf-8",
        )

        resolved = Path(asset_module.resolve_package_asset(urdf_path))

        assert link_calls
        assert replace_calls
        assert _load_urdf(resolved) >= 0


def test_cache_directory_is_absolute_when_temp_candidate_is_relative(monkeypatch):
    from gym_pybullet_drones.utils import assets as asset_module

    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="gpd-cache-root-test-") as temp_dir:
        cache_dir = None
        try:
            monkeypatch.chdir(temp_dir)
            Path("relative-cache").mkdir()
            monkeypatch.setattr(
                asset_module.tempfile, "gettempdir", lambda: "relative-cache"
            )
            monkeypatch.setenv("PUBLIC", temp_dir)
            monkeypatch.setattr(asset_module, "_CACHE_DIR", None)
            monkeypatch.setattr(asset_module, "_CACHE_PID", None)

            cache_dir = asset_module._process_cache_dir()
            assert cache_dir.is_absolute()
        finally:
            if cache_dir is not None:
                asset_module._cleanup_cache(cache_dir, os.getpid())
            monkeypatch.chdir(original_cwd)


def test_process_caches_are_distinct_loadable_and_cleaned_up():
    with tempfile.TemporaryDirectory(prefix="gpd-process-assets-test-") as temp_dir:
        assets_dir = Path(temp_dir) / "\u8d44\u4ea7"
        assets_dir.mkdir()
        shutil.copy2(_package_assets() / "cf2x.urdf", assets_dir / "cf2x.urdf")
        shutil.copy2(_package_assets() / "cf2.dae", assets_dir / "cf2.dae")
        asset_path = assets_dir / "cf2x.urdf"
        assert not str(asset_path).isascii()

        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue()
        processes = [
            context.Process(
                target=_load_packaged_urdf_in_child,
                args=(result_queue, str(asset_path)),
            )
            for _ in range(2)
        ]

        for process in processes:
            process.start()
        results = [result_queue.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
        result_queue.close()
        result_queue.join_thread()

        assert all(body >= 0 for _, _, body in results)
        paths = [Path(path) for _, path, _ in results]
        assert paths[0] != paths[1]
        assert all(str(path).isascii() for path in paths)
        assert all(not path.parents[1].exists() for path in paths)
