# Puente by Typers · instalador para Windows / Windows installer (MIT)
# Lo abre «Instalar en Windows.bat». Instala las librerías de Python, crea los accesos directos,
# ofrece abrir el firewall solo en la red de la casa y enciende el Puente.
$ErrorActionPreference = 'Stop'
$es = (Get-UICulture).TwoLetterISOLanguageName -eq 'es'
function T($textoEs, $textoEn) { if ($es) { $textoEs } else { $textoEn } }
function Preguntar($texto) { (Read-Host ("$texto " + (T '[S/n]' '[Y/n]'))) -notmatch '^(n|no)$' }
$raiz = Split-Path -Parent $PSScriptRoot
Write-Host ''
Write-Host '  PUENTE BY TYPERS' -ForegroundColor Cyan
Write-Host (T '  Del celular a tu computador por el Wi-Fi de la casa.' '  From your phone to your computer over your home Wi-Fi.')
Write-Host ''

# 1. Python 3.9 o más nuevo
$python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
$sirve = $false
if ($python) { & $python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null; $sirve = ($LASTEXITCODE -eq 0) }
if (-not $sirve) {
  Write-Host (T '1. Falta Python 3.9 o más nuevo. Instálalo desde python.org (marca «Add python.exe to PATH») y vuelve a abrir este instalador.' `
               '1. Python 3.9 or newer is missing. Install it from python.org (check «Add python.exe to PATH») and run this installer again.') -ForegroundColor Yellow
  Start-Process 'https://www.python.org/downloads/windows/'
  exit 1
}
Write-Host ((T '1. Python listo: ' '1. Python found: ') + (& $python --version))

# 2. Librerías (Pillow, pillow-heif, qrcode)
Write-Host (T '2. Instalando librerías...' '2. Installing libraries...')
& $python -m pip install --user --disable-pip-version-check -q -r (Join-Path $raiz 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Write-Host (T 'No se pudieron instalar las librerías (revisa tu internet).' 'Could not install the libraries (check your internet).') -ForegroundColor Red; exit 1 }
& $python (Join-Path $raiz 'puente.py') --version

# 3. Accesos directos
$conInicio = Preguntar (T '3. ¿Encender el Puente solo cada vez que prendas el PC?' '3. Start Puente automatically when Windows starts?')
& (Join-Path $PSScriptRoot 'crear-acceso-directo.ps1') -SinInicio:(-not $conInicio)

# 4. Firewall (solo red privada)
if (Preguntar (T '4. ¿Permitir el Puente en el firewall, solo en la red de tu casa? (pide administrador)' '4. Allow Puente through the firewall, home network only? (asks for admin)')) {
  & (Join-Path $PSScriptRoot 'permitir-firewall.ps1')
}

# 5. Encender
Write-Host (T '5. Encendiendo... La primera vez te pregunta qué carpeta compartir.' '5. Starting... The first time it asks which folder to share.') -ForegroundColor Green
Start-Process (Get-Command pythonw.exe).Source -ArgumentList "`"$(Join-Path $PSScriptRoot 'encender.pyw')`"", '--mostrar'
Write-Host (T 'Listo. Busca el ícono del Puente junto al reloj.' 'Done. Look for the Puente icon next to the clock.')
Write-Host (T 'Si Windows pregunta por el firewall, marca SOLO «Redes privadas».' 'If Windows asks about the firewall, tick ONLY «Private networks».') -ForegroundColor Yellow
