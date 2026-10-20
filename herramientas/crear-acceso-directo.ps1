# Puente by Typers: crea los accesos directos (con su ícono). / Creates the shortcuts (with icon).
#   - Escritorio / Desktop: «Puente» lo enciende junto al reloj y muestra el QR.
#   - Inicio de Windows / Startup: se enciende solo al prender el PC. Para quitarlo / to remove it: -SinInicio
# Uso / Usage: powershell -ExecutionPolicy Bypass -File herramientas\crear-acceso-directo.ps1 [-SinInicio]
param([switch]$SinInicio)
$es = (Get-UICulture).TwoLetterISOLanguageName -eq 'es'
function T($textoEs, $textoEn) { if ($es) { $textoEs } else { $textoEn } }
$raiz = Split-Path -Parent $PSScriptRoot
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) { Write-Host (T 'No encuentro pythonw.exe: instala Python primero.' 'pythonw.exe not found: install Python first.') -ForegroundColor Red; exit 1 }
$ws = New-Object -ComObject WScript.Shell

function Crear($ruta, $argumentos) {
  $ad = $ws.CreateShortcut($ruta)
  $ad.TargetPath = $pythonw
  $ad.Arguments = ('"' + (Join-Path $PSScriptRoot 'encender.pyw') + '" ' + $argumentos).Trim()
  $ad.WorkingDirectory = $raiz
  $ad.IconLocation = (Join-Path $PSScriptRoot 'puente.ico') + ',0'
  $ad.Description = 'Puente by Typers'
  $ad.Save()
  Write-Host ((T 'Listo: ' 'Done: ') + $ruta)
}

Crear (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Puente.lnk') '--mostrar'
$inicio = Join-Path ([Environment]::GetFolderPath('Startup')) 'Puente.lnk'
if ($SinInicio) {
  if (Test-Path $inicio) { Remove-Item $inicio; Write-Host (T 'Quitado del inicio de Windows.' 'Removed from Windows startup.') }
} else {
  Crear $inicio ''
}
