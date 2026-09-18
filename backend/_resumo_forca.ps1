$ErrorActionPreference = 'Continue'
$P = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$fontes = @(
 "Health\Apuração Meta 2026 Health - 18.09.xlsx",
 "Finance\Apuração Meta Finance (AE) - 18.09.xlsx",
 "Finance\Apuração Meta Finance (DIRETOR) - 18.09.xlsx",
 "Grupo Mult\Apuração Meta Grupo Mult - 18.09.xlsx",
 "Multisector\Apuração Meta Multisector - 18.09.xlsx",
 "Retail\Apuração Meta Retail (AE) - 18.09.xlsx",
 "Retail\Apuração Meta Retail (diretor) - 18.09.xlsx"
)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$abertos = @()
try {
  foreach ($f in $fontes) {
    $p2 = Join-Path $P $f
    if (Test-Path $p2) { $abertos += $xl.Workbooks.Open($p2, 0, $true); Write-Output ("aberto: {0}" -f (Split-Path $f -Leaf)) }
  }
  $wb = $xl.Workbooks.Open((Join-Path $P "RESUMO - 18.09.xlsx"), 3, $false)
  Start-Sleep -Seconds 2
  $xl.CalculateFullRebuild()
  Start-Sleep -Seconds 2
  $xl.CalculateFullRebuild()
  $wb.Save()
  Write-Output "RESUMO recalculado com as fontes abertas e salvo"
  $wb.Close($true)
} catch { Write-Output ("ERRO: {0}" -f $_.Exception.Message) }
finally {
  foreach ($w in $abertos) { try { $w.Close($false) } catch {} }
  try { $xl.Quit() } catch {}
  try { [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null } catch {}
}
