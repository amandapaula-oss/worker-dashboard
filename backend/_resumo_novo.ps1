# Cria o RESUMO novo apontando para as Apuracoes de 18.09 (resiliente).
$ErrorActionPreference = 'Continue'
$P = "$env:USERPROFILE\FCamara Consultoria e Formação\FCamara Files - CONTROLADORIA\30. FP&A NOVO\15. Metas (Apuração)\2026\Metas Oficiais"
$de_para = @{
  "Apuração Meta 2026 Health OFICIAL.xlsx"    = "Health\Apuração Meta 2026 Health - 18.09.xlsx"
  "Apuração Meta Finance (AE) OFICIAL.xlsx"   = "Finance\Apuração Meta Finance (AE) - 18.09.xlsx"
  "Apuração Meta Grupo Mult Oficial.xlsx"     = "Grupo Mult\Apuração Meta Grupo Mult - 18.09.xlsx"
  "Apuração Meta Multisector OFICIAL V3.xlsx" = "Multisector\Apuração Meta Multisector - 18.09.xlsx"
  "Apuração Meta Retail  (AE) OFICIAL.xlsx"   = "Retail\Apuração Meta Retail (AE) - 18.09.xlsx"
}
$src = Join-Path $P "RESUMO.xlsx"
$dst = Join-Path $P "RESUMO - 18.09.xlsx"
if (Test-Path $dst) { Remove-Item $dst -Force }
Copy-Item $src $dst -Force
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$wb = $null
try {
  $wb = $xl.Workbooks.Open($dst, 0, $false)
  $xl.Calculation = -4135
  $feitos = 0; $falhas = @()
  foreach ($nome in $de_para.Keys) {
    $novo = Join-Path $P $de_para[$nome]
    if (-not (Test-Path $novo)) { $falhas += "$nome (destino ausente)"; continue }
    $raw = $wb.LinkSources(1)
    $alvo = $null
    if ($null -ne $raw) { foreach ($x in $raw) { if ((Split-Path ([string]$x) -Leaf) -eq $nome) { $alvo = [string]$x } } }
    if ($null -eq $alvo) { Write-Output ("ja repontado ou ausente: {0}" -f $nome); continue }
    try {
      $wb.ChangeLink($alvo, $novo, 1) | Out-Null
      $feitos++
      Write-Output ("repontado: {0}" -f $nome)
    } catch {
      $falhas += "$nome ($($_.Exception.Message))"
      Write-Output ("FALHOU:    {0}" -f $nome)
    }
    Start-Sleep -Milliseconds 800
  }
  $xl.Calculation = -4105
  try { $wb.Application.CalculateFullRebuild() } catch { Write-Output "recalculo adiado" }
  $wb.Save()
  Write-Output ("--- repontados: {0} | falhas: {1}" -f $feitos, $falhas.Count)
  foreach ($f in $falhas) { Write-Output ("    ! {0}" -f $f) }
  $raw2 = $wb.LinkSources(1)
  Write-Output "links finais:"
  if ($null -ne $raw2) { foreach ($x in $raw2) { Write-Output ("    {0}" -f (Split-Path ([string]$x) -Leaf)) } }
} catch {
  Write-Output ("ERRO: {0}" -f $_.Exception.Message)
} finally {
  if ($null -ne $wb) { try { $wb.Close($true) } catch {} }
  try { $xl.Quit() } catch {}
  try { [Runtime.InteropServices.Marshal]::ReleaseComObject($xl) | Out-Null } catch {}
}
Write-Output "fim"
