Add-Type -AssemblyName System.IO.Compression.FileSystem

$filePath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$backupPath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup3.xlsx'
$tempPath = 'C:\Users\amanda.paula\Downloads\Racional_temp4.xlsx'

function Remove-Accents($str) {
    $norm = $str.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = [System.Text.StringBuilder]::new()
    foreach ($c in $norm.ToCharArray()) {
        if ([System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) { $sb.Append($c) | Out-Null }
    }
    return $sb.ToString().Normalize([System.Text.NormalizationForm]::FormC)
}
function Normalize-Name($name) {
    return (Remove-Accents ([regex]::Replace($name.Trim(), '\s+', ' '))).ToUpper()
}

Copy-Item -Path $filePath -Destination $backupPath -Force
Copy-Item -Path $filePath -Destination $tempPath -Force

$zip = [System.IO.Compression.ZipFile]::Open($tempPath, 'Update')

# Le sharedStrings
$ssEntry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/sharedStrings.xml' }
$r = New-Object System.IO.StreamReader($ssEntry.Open(), [System.Text.Encoding]::UTF8)
$ssContent = $r.ReadToEnd(); $r.Close()
[xml]$ssXml = $ssContent
$ssNs = New-Object System.Xml.XmlNamespaceManager($ssXml.NameTable)
$ssNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
$siList = $ssXml.SelectNodes("//x:si", $ssNs)
$ssMap = @{}
for ($i = 0; $i -lt $siList.Count; $i++) {
    $tNodes = $siList[$i].SelectNodes("x:t | x:r/x:t", $ssNs)
    $ssMap[$i] = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
}

# Le sheet1 (TimeAndExpenses)
$s1Entry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$r2 = New-Object System.IO.StreamReader($s1Entry.Open(), [System.Text.Encoding]::UTF8)
$s1Content = $r2.ReadToEnd(); $r2.Close()
[xml]$s1Xml = $s1Content
$s1Ns = New-Object System.Xml.XmlNamespaceManager($s1Xml.NameTable)
$s1Ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

# Helper: pega texto de celula shared string
function Get-SSText($cell, $ssMap, $ns) {
    if (-not $cell) { return "" }
    if ($cell.GetAttribute("t") -eq "s") {
        $v = $cell.SelectSingleNode("x:v", $ns)
        if ($v -and $ssMap.ContainsKey([int]$v.InnerText)) { return $ssMap[[int]$v.InnerText] }
    }
    elseif ($cell.GetAttribute("t") -eq "str" -or $cell.GetAttribute("t") -eq "inlineStr") {
        $v = $cell.SelectSingleNode("x:v", $ns)
        if ($v) { return $v.InnerText }
    }
    return ""
}

# Helper: extrai nomes normalizados de uma coluna de uma sheet
function Get-NormNamesFromSheet($zip, $sheetFile, $colLetter, $ssMap, $ssNs) {
    $entry = $zip.Entries | Where-Object { $_.FullName -eq "xl/$sheetFile" }
    if (-not $entry) { return @{} }
    $r = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8)
    $content = $r.ReadToEnd(); $r.Close()
    [xml]$xml = $content
    $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
    $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    $map = @{}
    $cells = $xml.SelectNodes("//x:c[starts-with(@r,'$colLetter') and @t='s']", $ns)
    foreach ($c in $cells) {
        $v = $c.SelectSingleNode("x:v", $ns)
        if (-not $v) { continue }
        $idx = [int]$v.InnerText
        if ($idx -lt $siList.Count) {
            $tNodes = $siList[$idx].SelectNodes("x:t | x:r/x:t", $ssNs)
            $raw = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
            if ($raw.Trim() -ne '') { $map[(Normalize-Name $raw)] = $true }
        }
    }
    return $map
}

# Nomes normalizados em cada aba de referencia
Write-Host "Carregando referencias..."
$paraDeMap = Get-NormNamesFromSheet $zip "worksheets/sheet5.xml" "C" $ssMap $ssNs  # PARA DE PESSOAS col C
$cltMap = Get-NormNamesFromSheet $zip "worksheets/sheet4.xml" "D" $ssMap $ssNs  # CUTOS CLTs col D
$pjMap = Get-NormNamesFromSheet $zip "worksheets/sheet3.xml" "B" $ssMap $ssNs  # CUSTOS PJs col B (worker_name)
Write-Host "PARA DE PESSOAS: $($paraDeMap.Count) | CLTs: $($cltMap.Count) | PJs: $($pjMap.Count)"

# Coluna R = indice 18 (A=1, B=2, ..., R=18)
# Verifica qual indice numerico R usa no XML (R = coluna 18)
# Namespace para criar elementos
$xmlNs = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

# Funcao para adicionar ou atualizar celula R em uma linha
function Set-ColR($row, $rowNum, $obsText, $s1Xml, $s1Ns, $xmlNs) {
    # Verifica se ja existe coluna R nesta linha
    $rRef = "R$rowNum"
    $existingR = $row.SelectSingleNode("x:c[@r='$rRef']", $s1Ns)
    if ($existingR) {
        # Ja existe observacao - nao sobrescreve
        $existingType = $existingR.GetAttribute("t")
        $existingV = $existingR.SelectSingleNode("x:v", $s1Ns)
        $existingIs = $existingR.SelectSingleNode("x:is", $s1Ns)
        if ($existingV -or $existingIs) { return $false }  # ja tem valor
    }

    if ($existingR) {
        $row.RemoveChild($existingR) | Out-Null
    }

    # Cria nova celula R com inlineStr
    $newCell = $s1Xml.CreateElement("c", $xmlNs)
    $newCell.SetAttribute("r", $rRef)
    $newCell.SetAttribute("t", "inlineStr")
    $isElem = $s1Xml.CreateElement("is", $xmlNs)
    $tElem = $s1Xml.CreateElement("t", $xmlNs)
    $tElem.InnerText = $obsText
    $isElem.AppendChild($tElem) | Out-Null
    $newCell.AppendChild($isElem) | Out-Null

    # Insere na posicao correta (apos coluna Q, antes de S)
    $inserted = $false
    $children = $row.SelectNodes("x:c", $s1Ns)
    foreach ($child in $children) {
        $childRef = $child.GetAttribute("r")
        $childCol = [regex]::Match($childRef, '^([A-Z]+)').Groups[1].Value
        # Compara colunas: R vem depois de Q (17), antes de S (19)
        if ($childCol -ge "S") {
            $row.InsertBefore($newCell, $child) | Out-Null
            $inserted = $true
            break
        }
    }
    if (-not $inserted) { $row.AppendChild($newCell) | Out-Null }
    return $true
}

# Itera todas as linhas do sheet1, encontra nomes sem match em PARA DE PESSOAS
$allRows = $s1Xml.SelectNodes("//x:row", $s1Ns)
$addedPJ = 0
$addedCLT = 0
$skipped = 0

foreach ($row in $allRows) {
    $rowNum = $row.GetAttribute("r")
    if ([int]$rowNum -le 2) { continue }  # pula cabecalho

    $colL = $row.SelectSingleNode("x:c[starts-with(@r,'L')]", $s1Ns)
    $lText = Get-SSText $colL $ssMap $s1Ns
    if ($lText.Trim() -eq '') { continue }

    $lNorm = Normalize-Name $lText

    # Pula se ja tem match em PARA DE PESSOAS
    if ($paraDeMap.ContainsKey($lNorm)) { continue }

    # Verifica se a linha ja tem observacao na coluna R
    $rRef = "R$rowNum"
    $existingR = $row.SelectSingleNode("x:c[@r='$rRef']", $s1Ns)
    if ($existingR) {
        $skipped++
        continue
    }

    # Sem match em PARA DE PESSOAS - verifica CLTs e PJs
    if ($cltMap.ContainsKey($lNorm)) {
        $added = Set-ColR $row $rowNum "ta nos clts e deveria estar no parade" $s1Xml $s1Ns $xmlNs
        if ($added) { $addedCLT++; Write-Host "CLT: $lText (linha $rowNum)" }
    }
    elseif ($pjMap.ContainsKey($lNorm)) {
        $added = Set-ColR $row $rowNum "ta no PJs e deveria estar no parade" $s1Xml $s1Ns $xmlNs
        if ($added) { $addedPJ++; Write-Host "PJ: $lText (linha $rowNum)" }
    }
}

Write-Host ""
Write-Host "Observacoes adicionadas: $addedCLT de CLTs, $addedPJ de PJs. Puladas (ja tinham): $skipped"

# Salva sheet1 de volta no ZIP
$s1Entry.Delete()
$newS1 = $zip.CreateEntry('xl/worksheets/sheet1.xml')
$w = New-Object System.IO.StreamWriter($newS1.Open(), [System.Text.Encoding]::UTF8)
$w.Write($s1Xml.OuterXml); $w.Close()

$zip.Dispose()
Copy-Item -Path $tempPath -Destination $filePath -Force
Remove-Item -Path $tempPath -Force
Write-Host "Arquivo salvo! Backup em: $backupPath"
