$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = "C:\Users\qq366410837\Downloads\《钢印》第一卷·旧神纪元：协同写作指令集.docx"
$doc = $word.Documents.Open($docPath)
$text = $doc.Content.Text
$doc.Close($false)
$word.Quit()
Write-Output $text