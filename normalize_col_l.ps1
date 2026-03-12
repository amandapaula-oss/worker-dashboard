Add-Type -AssemblyName System.IO.Compression.FileSystem

$filePath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1).xlsx'
$backupPath = 'C:\Users\amanda.paula\Downloads\Racional Tentativa yuri (1)_backup.xlsx'
$tempPath = 'C:\Users\amanda.paula\Downloads\Racional_temp2.xlsx'

# Backup
Copy-Item -Path $filePath -Destination $backupPath -Force
Write-Host "Backup criado: $backupPath"

Copy-Item -Path $filePath -Destination $tempPath -Force

# Funcao para remover acentos (normalizar para ASCII)
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

# Funcao para normalizar nome: trim + espaços duplos + sem acento + maiuscula
function Normalize-Name($name) {
    # Trim
    $n = $name.Trim()
    # Remove acentos
    $n = Remove-Accents $n
    # Colapsa espacos multiplos
    $n = [regex]::Replace($n, '\s+', ' ')
    return $n
}

# Abre ZIP em modo update
$zip = [System.IO.Compression.ZipFile]::Open($tempPath, 'Update')

$ssEntry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/sharedStrings.xml' }
$reader = New-Object System.IO.StreamReader($ssEntry.Open(), [System.Text.Encoding]::UTF8)
$ssContent = $reader.ReadToEnd()
$reader.Close()

$s1Entry = $zip.Entries | Where-Object { $_.FullName -eq 'xl/worksheets/sheet1.xml' }
$reader2 = New-Object System.IO.StreamReader($s1Entry.Open(), [System.Text.Encoding]::UTF8)
$s1Content = $reader2.ReadToEnd()
$reader2.Close()

[xml]$ssXml = $ssContent
$ssNs = New-Object System.Xml.XmlNamespaceManager($ssXml.NameTable)
$ssNs.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")
$siList = $ssXml.SelectNodes("//x:si", $ssNs)

[xml]$s1Xml = $s1Content
$s1Ns = New-Object System.Xml.XmlNamespaceManager($s1Xml.NameTable)
$s1Ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

# Descobre quais indices de sharedStrings sao usados pela coluna L
$lCells = $s1Xml.SelectNodes("//x:c[starts-with(@r,'L') and @t='s']", $s1Ns)
$lIndices = @{}
foreach ($c in $lCells) {
    $v = $c.SelectSingleNode("x:v", $s1Ns)
    if ($v) { $lIndices[[int]$v.InnerText] = $true }
}
Write-Host "Indices unicos na coluna L: $($lIndices.Keys.Count)"

# Normaliza apenas os sharedStrings usados pela coluna L
$changes = 0
foreach ($idx in $lIndices.Keys) {
    $si = $siList[$idx]
    
    # Pega todos os nos <t> (pode ter varios <r><t> para formatacao mista)
    $tNodes = $si.SelectNodes("x:t | x:r/x:t", $ssNs)
    
    if ($tNodes.Count -eq 1) {
        # Simples: so um <t>
        $original = $tNodes[0].InnerText
        $normalized = Normalize-Name $original
        if ($original -ne $normalized) {
            Write-Host "[$idx] '$original' -> '$normalized'"
            $tNodes[0].InnerText = $normalized
            # Remove xml:space="preserve" se existir (nao precisamos mais dele apos trim)
            $tNodes[0].RemoveAttribute("xml:space")
            $changes++
        }
    }
    elseif ($tNodes.Count -gt 1) {
        # Multiplos runs de texto (formatacao mista) - concatena e simplifica
        $fullText = ($tNodes | ForEach-Object { $_.InnerText }) -join ""
        $normalized = Normalize-Name $fullText
        $original = $fullText
        if ($original -ne $normalized) {
            Write-Host "[$idx] (multi-run) '$original' -> '$normalized'"
            # Coloca tudo no primeiro <t> e limpa os outros runs
            # Para simplificar, vamos reescrever o si com um unico <t>
            # Isso pode perder formatacao de fonte, mas e aceitavel para correcao de dados
            $tNodes[0].InnerText = $normalized
            $tNodes[0].RemoveAttribute("xml:space")
            for ($i = 1; $i -lt $tNodes.Count; $i++) {
                $tNodes[$i].InnerText = ""
            }
            $changes++
        }
    }
}

Write-Host "`nTotal de sharedStrings alterados: $changes"

# Salva sharedStrings.xml de volta
$ssEntry.Delete()
$newSsEntry = $zip.CreateEntry('xl/sharedStrings.xml')
$writer = New-Object System.IO.StreamWriter($newSsEntry.Open(), [System.Text.Encoding]::UTF8)
$writer.Write($ssXml.OuterXml)
$writer.Close()

$zip.Dispose()

# Substitui arquivo original
Copy-Item -Path $tempPath -Destination $filePath -Force
Remove-Item -Path $tempPath -Force

Write-Host "Arquivo salvo com sucesso!"
Write-Host "Feito! $changes nomes normalizados na coluna L."
