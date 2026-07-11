param(
    [Parameter(Mandatory = $true)]
    [string]$DocxPath,
    [Parameter(Mandatory = $true)]
    [string]$PdfPath
)

$docx = (Resolve-Path -LiteralPath $DocxPath).Path
$pdf = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($PdfPath)
$word = New-Object -ComObject Word.Application
$word.Visible = $false

try {
    $doc = $word.Documents.Open($docx)
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close()
    Write-Output "pdf=$pdf"
}
finally {
    $word.Quit()
}
