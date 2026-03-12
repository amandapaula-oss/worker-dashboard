Add-Type -AssemblyName System.IO.Compression.FileSystem

$filePath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri.xlsx'
$backupPath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri_backup.xlsx'
$tempPath = 'C:\Users\amanda.paula\Downloads\Racional_temp_edit.xlsx'

# Faz backup do original
Copy-Item -Path $filePath -Destination $backupPath -Force
Write-Host "Backup criado: $backupPath"

# Copia para temp
Copy-Item -Path $filePath -Destination $tempPath -Force

# Le sheet1.xml
$zip = [System.IO.Compression.ZipFile]::Open($tempPath, 'Update')
$sheet1Entry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$reader = New-Object System.IO.StreamReader($sheet1Entry.Open(), [System.Text.Encoding]::UTF8)
$sheet1Content = $reader.ReadToEnd()
$reader.Close()

# Substitui valores inlineStr na coluna L:
# Padrao: <c r="Lxx" ... t="inlineStr"><is><t>  VALOR  </t></is></c>
# Tambem pode ter xml:space="preserve" no <t>

$trimCount = 0
$newContent = [regex]::Replace(
    $sheet1Content,
    '(<c r="L\d+"[^>]*t="inlineStr"[^>]*>(?:<is>)<t(?:[^>]*)>)([ \t]+)(.*?)([ \t]*)(<\/t>)',
    {
        param($m)
        $prefix = $m.Groups[1].Value
        $leadSpace = $m.Groups[2].Value
        $middle = $m.Groups[3].Value
        $trailSpace = $m.Groups[4].Value
        $suffix = $m.Groups[5].Value
        $script:trimCount++
        # Remove espacos do início e retorna sem eles
        "$prefix$middle$suffix"
    },
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)

# Tambem trata o caso de so ter trailing space (sem leading)
$newContent2 = [regex]::Replace(
    $newContent,
    '(<c r="L\d+"[^>]*t="inlineStr"[^>]*>(?:<is>)<t(?:[^>]*)>)(.*?)([ \t]+)(<\/t>)',
    {
        param($m)
        $prefix = $m.Groups[1].Value
        $middle = $m.Groups[2].Value
        $trailSpace = $m.Groups[3].Value
        $suffix = $m.Groups[4].Value
        $script:trimCount++
        "$prefix$middle$suffix"
    },
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)

Write-Host "Celulas ajustadas: $trimCount"

# Substitui o sheet1.xml no ZIP
$sheet1Entry.Delete()
$newEntry = $zip.CreateEntry('xl/worksheets/sheet1.xml')
$writer = New-Object System.IO.StreamWriter($newEntry.Open(), [System.Text.Encoding]::UTF8)
$writer.Write($newContent2)
$writer.Close()
$zip.Dispose()

# Substitui o arquivo original
Copy-Item -Path $tempPath -Destination $filePath -Force
Remove-Item -Path $tempPath -Force

Write-Host "Concluido! Arquivo salvo: $filePath"
