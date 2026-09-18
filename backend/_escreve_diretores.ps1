# Gera as copias novas das Apuracoes com a aba nova_base_calculada atualizada.
# Instancia propria do Excel — NUNCA mexe na instancia da Amanda.
$ErrorActionPreference = 'Continue'
$P  = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$G  = "C:\Users\AMANDA~1.PAU\AppData\Local\Temp\claude\c--Users-amanda-paula-worker-dashboard\e41ea9d5-1d78-4580-8ef0-dd877eefb38b\scratchpad\metas\grade"
$mapa = @(
  @{ orig = "Finance\Apuração Meta Finance (DIRETOR).xlsx";       novo = "Finance\Apuração Meta Finance (DIRETOR) - 18.09.xlsx";  bu = "DIR_Finance" }
  @{ orig = "Retail\Apuração Meta Retail  (diretor) Oficial2.xlsx"; novo = "Retail\Apuração Meta Retail (diretor) - 18.09.xlsx";  bu = "DIR_Retail" }
)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
try {
  foreach ($m in $mapa) {
    $src = Join-Path $P $m.orig; $dst = Join-Path $P $m.novo
    $gra = Join-Path $G "$($m.bu).xlsx"
    if (-not (Test-Path $src)) { Write-Output "!! nao achou $($m.orig)"; continue }
    if (-not (Test-Path $gra)) { Write-Output "!! nao achou grade $($m.bu)"; continue }
    Copy-Item $src $dst -Force
    $wb = $xl.Workbooks.Open($dst, 0, $false)
    Start-Sleep -Milliseconds 700
    try { $xl.Calculation = -4135 } catch { Write-Output '  (calculo manual nao aplicado)' }
    $wg = $xl.Workbooks.Open($gra, 0, $true)
    $ws = $wb.Worksheets.Item("nova_base_calculada")
    $lo = $ws.ListObjects.Item(1)
    $hdrRow = $lo.HeaderRowRange.Row
    $col1   = $lo.Range.Column
    $nCols  = $lo.ListColumns.Count
    $gs = $wg.Worksheets.Item(1)
    $nRows = $gs.UsedRange.Rows.Count - 1          # tira o cabecalho
    $oldRows = if ($lo.DataBodyRange) { $lo.DataBodyRange.Rows.Count } else { 0 }
    if ($lo.DataBodyRange) { $lo.DataBodyRange.ClearContents() | Out-Null }
    $novoFim = $ws.Cells.Item($hdrRow + $nRows, $col1 + $nCols - 1)
    $lo.Resize($ws.Range($ws.Cells.Item($hdrRow, $col1), $novoFim)) | Out-Null
    $orig = $gs.Range($gs.Cells.Item(2,1), $gs.Cells.Item($nRows + 1, $nCols))
    $orig.Copy() | Out-Null
    $alvo = $ws.Cells.Item($hdrRow + 1, $col1)
    $alvo.PasteSpecial(-4163) | Out-Null    # xlPasteValues
    $wg.Close($false)
    try { $xl.Calculation = -4105 } catch {}
    $wb.Application.CalculateFullRebuild()
    $wb.Save(); $wb.Close($true)
    Write-Output ("OK  {0,-18} {1} -> {2} linhas" -f $m.bu, $oldRows, $nRows)
  }
} finally {
  $xl.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null
}
Write-Output "concluido"
