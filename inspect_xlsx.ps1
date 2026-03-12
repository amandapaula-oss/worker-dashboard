Add-Type -AssemblyName System.IO.Compression.FileSystem

# Compara coluna R do arquivo atual vs backup2
function Get-RCells($path) {
    $zip = [System.IO.Compression.ZipFile]::Open($path, 'Read')

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

    $s1Entry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
    $r2 = New-Object System.IO.StreamReader($s1Entry.Open(), [System.Text.Encoding]::UTF8)
    $s1Content = $r2.ReadToEnd(); $r2.Close()
    $zip.Dispose()

    [xml]$s1Xml = $s1Content
    $s1Ns = New-Object System.Xml.XmlNamespaceManager($s1Xml.NameTable)
    $s1Ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

    $results = @()
    $rCells = $s1Xml.SelectNodes("//x:c[starts-with(@r,'R') and string-length(@r) > 1]", $s1Ns)
    foreach ($c in $rCells) {
        $ref = $c.GetAttribute("r")
        # So queremos coluna R (nao RA, RB etc)
        if ($ref -notmatch '^R\d+$') { continue }
        $t = $c.GetAttribute("t")
        $v = $c.SelectSingleNode("x:v", $s1Ns)
        $isNode = $c.SelectSingleNode("x:is/x:t", $s1Ns)
        $val = ""
        if ($t -eq "s" -and $v -and $ssMap.ContainsKey([int]$v.InnerText)) {
            $val = $ssMap[[int]$v.InnerText]
        }
        elseif ($isNode) {
            $val = $isNode.InnerText
        }
        elseif ($v) {
            $val = $v.InnerText
        }
        if ($val.Trim() -ne "") {
            $results += [PSCustomObject]@{ Ref = $ref; Val = $val }
        }
    }
    return $results
}

$current = Get-RCells 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$backup2 = Get-RCells 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup2.xlsx'

Write-Host "=== Col R no arquivo ATUAL ($($current.Count) celulas com valor) ==="
$current | ForEach-Object { Write-Host "  $($_.Ref): $($_.Val)" }

Write-Host "`n=== Col R no BACKUP2 ($($backup2.Count) celulas com valor) ==="
$backup2 | ForEach-Object { Write-Host "  $($_.Ref): $($_.Val)" }
