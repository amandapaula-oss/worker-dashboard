Add-Type -AssemblyName System.IO.Compression.FileSystem

$filePath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$zip = [System.IO.Compression.ZipFile]::Open($filePath, 'Read')

function Remove-Accents($str) {
    $normalized = $str.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = [System.Text.StringBuilder]::new()
    foreach ($c in $normalized.ToCharArray()) {
        $cat = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c)
        if ($cat -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) {
            $sb.Append($c) | Out-Null
        }
    }
    return $sb.ToString().Normalize([System.Text.NormalizationForm]::FormC)
}

function Normalize-Name($name) {
    $n = $name.Trim()
    $n = Remove-Accents $n
    $n = [regex]::Replace($n, '\s+', ' ')
    return $n.ToUpper()
}

function Get-ColTexts($zip, $sheetFile, $colLetter, $ssMap) {
    $entry = $zip.Entries | Where-Object { $_.FullName -eq "xl/$sheetFile" }
    if (-not $entry) { return @() }
    $reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
    $content = $reader.ReadToEnd()
    $reader.Close()
    [xml]$xml = $content
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    $cells = $xml.SelectNodes("//x:c[starts-with(@r,'$colLetter') and (@t='s' or @t='inlineStr')]", $ns)
    $texts = @()
    foreach ($c in $cells) {
        $t = $c.GetAttribute("t")
        if ($t -eq 's') {
            $v = $c.SelectSingleNode("x:v", $ns)
            if ($v -and $ssMap.ContainsKey([int]$v.InnerText)) {
                $txt = $ssMap[[int]$v.InnerText]
                if ($txt -and $txt.Trim() -ne '') { $texts += $txt }
            }
        }
        elseif ($t -eq 'inlineStr') {
            $tNode = $c.SelectSingleNode("x:is/x:t", $ns)
            if ($tNode -and $tNode.InnerText.Trim() -ne '') { $texts += $tNode.InnerText }
        }
    }
    return $texts
}

# Le sharedStrings
$ssEntry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/sharedStrings.xml' }
$reader = New-Object System.IO.StreamReader($ssEntry.Open(), [System.Text.Encoding]::UTF8)
$ssContent = $reader.ReadToEnd()
$reader.Close()
[xml]$ssXml = $ssContent
$ssNs = New-Object System.Xml.XmlNamespaceManager($ssXml.NameTable)
$ssNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
$siList = $ssXml.SelectNodes("//x:si", $ssNs)
$ssMap = @{}
for ($i = 0; $i -lt $siList.Count; $i++) {
    $tNodes = $siList[$i].SelectNodes("x:t | x:r/x:t", $ssNs)
    $ssMap[$i] = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
}

$lTexts = Get-ColTexts $zip "worksheets/sheet1.xml" "L" $ssMap
$cltTexts = Get-ColTexts $zip "worksheets/sheet4.xml" "D" $ssMap
$pessoasTexts = Get-ColTexts $zip "worksheets/sheet5.xml" "C" $ssMap
$zip.Dispose()

Write-Host "Coluna L: $($lTexts.Count) | CLTs: $($cltTexts.Count) | Pessoas: $($pessoasTexts.Count)"

$lNorm = $lTexts       | ForEach-Object { Normalize-Name $_ }
$cltNorm = $cltTexts     | ForEach-Object { Normalize-Name $_ } | Sort-Object -Unique
$pessoasNorm = $pessoasTexts | ForEach-Object { Normalize-Name $_ } | Sort-Object -Unique
$allRef = ($cltNorm + $pessoasNorm) | Sort-Object -Unique

Write-Host "Referencias unicas normalizadas: $($allRef.Count)"

# Levenshtein com array 1D (compativel com PowerShell)
function Get-Levenshtein($s, $t) {
    $sl = $s.Length; $tl = $t.Length
    if ($sl -eq 0) { return $tl }
    if ($tl -eq 0) { return $sl }
    $prev = 0..$tl
    for ($i = 1; $i -le $sl; $i++) {
        $curr = New-Object int[] ($tl + 1)
        $curr[0] = $i
        for ($j = 1; $j -le $tl; $j++) {
            $cost = if ($s[$i - 1] -eq $t[$j - 1]) { 0 } else { 1 }
            $del = $curr[$j - 1] + 1
            $ins = $prev[$j] + 1
            $sub = $prev[$j - 1] + $cost
            $min = $del
            if ($ins -lt $min) { $min = $ins }
            if ($sub -lt $min) { $min = $sub }
            $curr[$j] = $min
        }
        $prev = $curr
    }
    return $prev[$tl]
}

$lUniq = $lNorm | Sort-Object -Unique
$sb = [System.Text.StringBuilder]::new()
$sb.AppendLine("NOME_COLUNA_L`tMELHOR_MATCH_REFERENCIA`tDISTANCIA`tSIMILARIDADE_PCT") | Out-Null

$noMatchCount = 0
foreach ($lName in $lUniq) {
    if ($allRef -contains $lName) { continue }
    $bestDist = 9999
    $bestMatch = ""
    foreach ($ref in $allRef) {
        $lenDiff = [Math]::Abs($lName.Length - $ref.Length)
        if ($lenDiff -gt 20) { continue }
        $dist = Get-Levenshtein $lName $ref
        if ($dist -lt $bestDist) {
            $bestDist = $dist
            $bestMatch = $ref
        }
    }
    $maxLen = [Math]::Max($lName.Length, $bestMatch.Length)
    $sim = if ($maxLen -gt 0) { [Math]::Round((1 - $bestDist / $maxLen) * 100, 1) } else { 100 }
    $sb.AppendLine("$lName`t$bestMatch`t$bestDist`t$sim") | Out-Null
    $noMatchCount++
}

[System.IO.File]::WriteAllText('C:\Users\amanda.paula\Downloads\fuzzy_match_report.tsv', $sb.ToString(), [System.Text.Encoding]::UTF8)
Write-Host "Relatorio salvo! $noMatchCount nomes sem match exato de $($lUniq.Count) unicos."
