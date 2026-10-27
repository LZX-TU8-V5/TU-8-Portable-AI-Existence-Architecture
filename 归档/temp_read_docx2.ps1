# Try to open and repair the document
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = $false  # Suppress alerts

$docPath = "C:\Users\qq366410837\Downloads\《钢印》第一卷·旧神纪元：协同写作指令集.docx"

try {
    # Try opening with repair
    $doc = $word.Documents.Open($docPath, $false, $true, $false, $null, $null, $null, $null, $null, $null, $null, $true)
    $text = $doc.Content.Text
    Write-Output $text
} catch {
    Write-Output "Error: $_"
} finally {
    if ($doc) { $doc.Close($false) }
    $word.Quit()
}