param([string]$Nome, [string]$Rel)
$ErrorActionPreference = 'Continue'
$P = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$dst = Join-Path $P "RESUMO - 18.09.xlsx"
$novo = Join-Path $P $Rel
if (-not (Test-Path $novo)) { Write-Output "destino ausente: $Rel"; exit 1 }
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$wb = $null
try {
  $wb = $xl.Workbooks.Open($dst, 0, $false)
  $xl.Calculation = -4135
  $raw = $wb.LinkSources(1); $alvo = $null
  if ($null -ne $raw) { foreach ($x in $raw) { if ((Split-Path ([string]$x) -Leaf) -eq $Nome) { $alvo = [string]$x } } }
  if ($null -eq $alvo) { Write-Output "ja repontado: $Nome" }
  else {
    $ok = $false
    for ($i = 1; $i -le 5 -and -not $ok; $i++) {
      try { $wb.ChangeLink($alvo, $novo, 1) | Out-Null; $ok = $true; Write-Output "repontado (tentativa $i): $Nome" }
      catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ok) { Write-Output "FALHOU apos 5 tentativas: $Nome" }
  }
  $xl.Calculation = -4105
  $wb.Save()
} catch { Write-Output ("ERRO: {0}" -f $_.Exception.Message) }
finally {
  if ($null -ne $wb) { try { $wb.Close($true) } catch {} }
  try { $xl.Quit() } catch {}
  try { [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null } catch {}
}
