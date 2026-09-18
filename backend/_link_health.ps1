$ErrorActionPreference = 'Continue'
$P = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$dst  = Join-Path $P "RESUMO - 18.09.xlsx"
$novo = Join-Path $P "Health\Apuração Meta 2026 Health - 18.09.xlsx"
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$wb = $null
try {
  $wb = $xl.Workbooks.Open($dst, 0, $false)
  $xl.Calculation = -4135
  $raw = $wb.LinkSources(1); $alvo = $null
  foreach ($x in $raw) { if ((Split-Path ([string]$x) -Leaf) -like "*Health*OFICIAL*") { $alvo = [string]$x } }
  if ($null -eq $alvo) { Write-Output "Health ja esta repontado" }
  else {
    Write-Output ("origem: {0}" -f $alvo)
    for ($i=1; $i -le 5; $i++) {
      try { $wb.ChangeLink($alvo, $novo, 1) | Out-Null; Write-Output "ChangeLink ok (tentativa $i)"; break }
      catch { Start-Sleep -Seconds 2 }
    }
  }
  $xl.Calculation = -4105
  $wb.Save()
  Write-Output "--- conferindo NA MESMA sessao, depois do save ---"
  foreach ($x in $wb.LinkSources(1)) { Write-Output ("   {0}" -f (Split-Path ([string]$x) -Leaf)) }
} catch { Write-Output ("ERRO: {0}" -f $_.Exception.Message) }
finally {
  if ($null -ne $wb) { try { $wb.Close($true) } catch {} }
  try { $xl.Quit() } catch {}
  try { [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null } catch {}
}
