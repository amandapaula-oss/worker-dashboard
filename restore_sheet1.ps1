Add-Type -AssemblyName System.IO.Compression.FileSystem

$current = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$backup2 = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup2.xlsx'
$backupFinal = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup_antes_restore.xlsx'
$tempPath = 'C:\Users\amanda.paula\Downloads\Racional_restore.xlsx'

# Backup do estado atual antes de alterar
Copy-Item -Path $current -Destination $backupFinal -Force
Write-Host "Backup do estado atual salvo em: $backupFinal"

# Estrategia: pegar sheet1.xml do backup2 (que tem obs originais intactas)
# e mesclar com o sharedStrings.xml do arquivo atual (que tem as normalizacoes feitas)

# 1. Le sheet1.xml do backup2
$zipB2 = [System.IO.Compression.ZipFile]::Open($backup2, 'Read')
$s1EntryB2 = $zipB2.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$rB2 = New-Object System.IO.StreamReader($s1EntryB2.Open(), [System.Text.Encoding]::UTF8)
$s1FromBackup2 = $rB2.ReadToEnd(); $rB2.Close()
$zipB2.Dispose()

Write-Host "sheet1.xml do backup2 lido ($('{0:N0}' -f $s1FromBackup2.Length) chars)"

# 2. Copia o arquivo atual para temp e substitui sheet1.xml pelo do backup2
Copy-Item -Path $current -Destination $tempPath -Force

$zipUpdate = [System.IO.Compression.ZipFile]::Open($tempPath, 'Update')
$s1Entry = $zipUpdate.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$s1Entry.Delete()
$newS1 = $zipUpdate.CreateEntry('xl/worksheets/sheet1.xml')
$w = New-Object System.IO.StreamWriter($newS1.Open(), [System.Text.Encoding]::UTF8)
$w.Write($s1FromBackup2)
$w.Close()
$zipUpdate.Dispose()

# 3. Verifica se o restore funcionou - le as celulas R do arquivo restaurado
$zipCheck = [System.IO.Compression.ZipFile]::Open($tempPath, 'Read')
$ssE = $zipCheck.Entries | Where-Object { $_.FullName -eq 'xl/sharedStrings.xml' }
$rSS = New-Object System.IO.StreamReader($ssE.Open(), [System.Text.Encoding]::UTF8)
$ssContent = $rSS.ReadToEnd(); $rSS.Close()
[xml]$ssXml = $ssContent
$ssNs = New-Object System.Xml.XmlNamespaceManager($ssXml.NameTable)
$ssNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
$siList = $ssXml.SelectNodes("//x:si", $ssNs)
$ssMap = @{}
for ($i = 0; $i -lt $siList.Count; $i++) {
    $tNodes = $siList[$i].SelectNodes("x:t | x:r/x:t", $ssNs)
    $ssMap[$i] = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
}

$s1E = $zipCheck.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$rS1 = New-Object System.IO.StreamReader($s1E.Open(), [System.Text.Encoding]::UTF8)
$s1Content = $rS1.ReadToEnd(); $rS1.Close()
$zipCheck.Dispose()

[xml]$s1Xml = $s1Content
$s1Ns = New-Object System.Xml.XmlNamespaceManager($s1Xml.NameTable)
$s1Ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

$rCells = $s1Xml.SelectNodes("//x:c[matches(@r,'^R\d+$')]", $s1Ns)
# Alternativa sem XPATH 2.0:
$rMatches = [regex]::Matches($s1Content, '<c r="R(\d+)"[^>]*>.*?</c>', [System.Text.RegularExpressions.RegexOptions]::Singleline)
$obsCount = 0
Write-Host "`n=== Observacoes na coluna R apos restore ==="
foreach ($m in $rMatches) {
    $rowNum = $m.Groups[1].Value
    $cellXml = $m.Value
    # Verifica se tem valor
    if ($cellXml -match '<v>(\d+)</v>') {
        $idx = [int]$Matches[1]
        if ($ssMap.ContainsKey($idx)) {
            $val = $ssMap[$idx]
            if ($val -match "parade|pjs|clts|PJs|CLTs") {
                Write-Host "  R$rowNum = $val"
                $obsCount++
            }
        }
    }
}
Write-Host "Total de obs 'parade/pjs/clts': $obsCount"

# 4. Sobrescreve o arquivo atual com o restaurado
Copy-Item -Path $tempPath -Destination $current -Force
Remove-Item -Path $tempPath -Force
Write-Host "`nArquivo restaurado com sheet1 do backup2!"
Write-Host "sharedStrings (normalizacoes) mantidos do arquivo atual."
