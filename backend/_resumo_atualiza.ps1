$ErrorActionPreference = 'Continue'
$P = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$dst = Join-Path $P "RESUMO - 18.09.xlsx"
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$wb = $null
try {
  $wb = $xl.Workbooks.Open($dst, 3, $false)     # 3 = UpdateLinks
  try { $wb.UpdateLink() } catch { Write-Output "UpdateLink adiado" }
  $xl.CalculateFullRebuild()
  $wb.Save()
  Write-Output "links atualizados e salvo"
  $raw = $wb.LinkSources(1)
  if ($null -ne $raw) { foreach ($x in $raw) { Write-Output ("  link: {0}" -f (Split-Path ([string]$x) -Leaf)) } }
} catch { Write-Output ("ERRO: {0}" -f $_.Exception.Message) }
finally {
  if ($null -ne $wb) { try { $wb.Close($true) } catch {} }
  try { $xl.Quit() } catch {}
  try { [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null } catch {}
}
