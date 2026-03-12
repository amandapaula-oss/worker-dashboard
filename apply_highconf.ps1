Add-Type -AssemblyName System.IO.Compression.FileSystem

$filePath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$backupPath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup2.xlsx'
$tempPath = 'C:\Users\amanda.paula\Downloads\Racional_temp3.xlsx'
$tsvPath = 'C:\Users\amanda.paula\Downloads\fuzzy_match_report.tsv'

# Funcoes de normalizacao (identicas as usadas no fuzzy_match.ps1)
function Remove-Accents($str) {
    $norm = $str.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = [System.Text.StringBuilder]::new()
    foreach ($c in $norm.ToCharArray()) {
        $cat = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c)
        if ($cat -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) { $sb.Append($c) | Out-Null }
    }
    return $sb.ToString().Normalize([System.Text.NormalizationForm]::FormC)
}
function Normalize-Name($name) {
    $n = [regex]::Replace($name.Trim(), '\s+', ' ')
    return (Remove-Accents $n).ToUpper()
}

# Le o relatorio fuzzy
$tsvLines = [System.IO.File]::ReadAllLines($tsvPath, [System.Text.Encoding]::UTF8)
$highConf = @()
$lowConf = @()
foreach ($line in ($tsvLines | Select-Object -Skip 1)) {
    $parts = $line -split "`t"
    if ($parts.Count -lt 4) { continue }
    $sim = [double]$parts[3]
    if ($sim -ge 90) { $highConf += [PSCustomObject]@{ FromNorm = $parts[0]; ToNorm = $parts[1]; Sim = $sim } }
    else { $lowConf += [PSCustomObject]@{ FromNorm = $parts[0]; ToNorm = $parts[1]; Sim = $sim } }
}
Write-Host "Alta confianca (>=90%): $($highConf.Count)"
Write-Host "Baixa confianca (<90%): $($lowConf.Count)"
Write-Host ""
Write-Host "=== Substituicoes de ALTA confianca que serao aplicadas ==="
$highConf | ForEach-Object { Write-Host "  '$($_.FromNorm)' -> '$($_.ToNorm)' ($($_.Sim)%)" }
Write-Host ""
Write-Host "=== Casos de BAIXA confianca (nao alterados) ==="
$lowConf | ForEach-Object { Write-Host "  '$($_.FromNorm)' - melhor match: '$($_.ToNorm)' ($($_.Sim)%)" }

if ($highConf.Count -eq 0) {
    Write-Host "Nada a aplicar."
    exit
}

# Backup e copia temp
Copy-Item -Path $filePath -Destination $backupPath -Force
Copy-Item -Path $filePath -Destination $tempPath   -Force

$zip = [System.IO.Compression.ZipFile]::Open($tempPath, 'Update')

# Le sharedStrings
$ssEntry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/sharedStrings.xml' }
$reader = New-Object System.IO.StreamReader($ssEntry.Open(), [System.Text.Encoding]::UTF8)
$ssContent = $reader.ReadToEnd()
$reader.Close()
[xml]$ssXml = $ssContent
$ssNs = New-Object System.Xml.XmlNamespaceManager($ssXml.NameTable)
$ssNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
$siList = $ssXml.SelectNodes("//x:si", $ssNs)

# Le sheet1 para saber quais indices pertencem a coluna L
$s1Entry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$reader2 = New-Object System.IO.StreamReader($s1Entry.Open(), [System.Text.Encoding]::UTF8)
$s1Content = $reader2.ReadToEnd()
$reader2.Close()
[xml]$s1Xml = $s1Content
$s1Ns = New-Object System.Xml.XmlNamespaceManager($s1Xml.NameTable)
$s1Ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

$lCells = $s1Xml.SelectNodes("//x:c[starts-with(@r,'L') and @t='s']", $s1Ns)
$lIndices = @{}
foreach ($c in $lCells) {
    $v = $c.SelectSingleNode("x:v", $s1Ns)
    if ($v) { $lIndices[[int]$v.InnerText] = $true }
}

# Para cada sharedString da coluna L, verifica se tem match de alta confianca
# e substitui pelo valor do ToNorm (mas mantendo o casing do match da referencia)
# Para isso, precisamos encontrar o sharedString da referencia cujo normalized = ToNorm

# Primeiro, constroi mapa: normalized -> raw text dos sharedStrings de referencia (sheet4 col D, sheet5 col C)
function Get-RefRawTexts($zip, $sheetFile, $colLetter, $siList, $ssNs) {
    $entry = $zip.Entries | Where-Object { $_.FullName -eq "xl/$sheetFile" }
    if (-not $entry) { return @{} }
    $r = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
    $xml = [xml]$r.ReadToEnd(); $r.Close()
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    $map = @{}
    $cells = $xml.SelectNodes("//x:c[starts-with(@r,'$colLetter') and @t='s']", $ns)
    foreach ($c in $cells) {
        $v = $c.SelectSingleNode("x:v", $ns)
        if (-not $v) { continue }
        $idx = [int]$v.InnerText
        if ($idx -ge $siList.Count) { continue }
        $tNodes = $siList[$idx].SelectNodes("x:t | x:r/x:t", $ssNs)
        $raw = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
        if ($raw.Trim() -ne '') {
            $normKey = Normalize-Name $raw
            if (-not $map.ContainsKey($normKey)) { $map[$normKey] = $raw }
        }
    }
    return $map
}

$refMap = @{}
$cltMap = Get-RefRawTexts $zip "worksheets/sheet4.xml" "D" $siList $ssNs
$pessoasMap = Get-RefRawTexts $zip "worksheets/sheet5.xml" "C" $siList $ssNs
foreach ($k in $cltMap.Keys) { $refMap[$k] = $cltMap[$k] }
foreach ($k in $pessoasMap.Keys) { if (-not $refMap.ContainsKey($k)) { $refMap[$k] = $pessoasMap[$k] } }
Write-Host "`nReferencias mapeadas: $($refMap.Count)"

# Aplica substituicoes de alta confianca
$applied = 0
foreach ($idx in ($lIndices.Keys | Sort-Object)) {
    $si = $siList[$idx]
    $tNodes = $si.SelectNodes("x:t | x:r/x:t", $ssNs)
    $raw = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
    $norm = Normalize-Name $raw

    $match = $highConf | Where-Object { $_.FromNorm -eq $norm } | Select-Object -First 1
    if (-not $match) { continue }

    # Encontra o texto original da referencia
    $refRaw = $refMap[$match.ToNorm]
    if (-not $refRaw) {
        Write-Host "  [AVISO] Nao achou texto de referencia para '$($match.ToNorm)' - pulando"
        continue
    }

    Write-Host "  APLICADO: '$raw' -> '$refRaw' ($($match.Sim)%)"
    if ($tNodes.Count -ge 1) {
        $tNodes[0].InnerText = $refRaw
        $tNodes[0].RemoveAttribute("xml:space")
        for ($i = 1; $i -lt $tNodes.Count; $i++) { $tNodes[$i].InnerText = "" }
    }
    $applied++
}

Write-Host "`nTotal aplicado: $applied substituicoes"

if ($applied -gt 0) {
    $ssEntry.Delete()
    $newSs = $zip.CreateEntry('xl/sharedStrings.xml')
    $w = New-Object System.IO.StreamWriter($newSs.Open(), [System.Text.Encoding]::UTF8)
    $w.Write($ssXml.OuterXml); $w.Close()
}
$zip.Dispose()

Copy-Item -Path $tempPath -Destination $filePath -Force
Remove-Item -Path $tempPath -Force
Write-Host "Arquivo salvo! Backup em: $backupPath"
