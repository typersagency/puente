# Puente by Typers: deja pasar el Puente en el Firewall de Windows SOLO en redes privadas (la de la casa)
# y solo desde equipos de la misma red. En redes públicas (cafés, hoteles) sigue cerrado.
# Allows Puente through Windows Firewall ONLY on private networks and only from the same local network.
# Uso / Usage: powershell -ExecutionPolicy Bypass -File herramientas\permitir-firewall.ps1   (pide administrador / asks for admin)
$ErrorActionPreference = 'Stop'
$es = (Get-UICulture).TwoLetterISOLanguageName -eq 'es'
function T($textoEs, $textoEn) { if ($es) { $textoEs } else { $textoEn } }
$raiz = Split-Path -Parent $PSScriptRoot
$puerto = (Get-Content (Join-Path $raiz 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json).puerto
$local = Join-Path $raiz 'config.local.json'
if (Test-Path $local) { $l = Get-Content $local -Raw -Encoding UTF8 | ConvertFrom-Json; if ($l.puerto) { $puerto = $l.puerto } }
$nombre = 'Puente by Typers (red privada / private network)'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
  Write-Host (T 'Hace falta permiso de administrador. Se abre una ventana para pedirlo...' 'Administrator permission is needed. A window will ask for it...')
  Start-Process powershell -Verb RunAs -ArgumentList "-NoExit -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}

Get-NetFirewallRule -DisplayName $nombre -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $nombre -Description 'Puente by Typers: phone -> computer over the local network. Private profile and local subnet only.' `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort $puerto -Profile Private -RemoteAddress LocalSubnet | Out-Null
Write-Host (T "Listo: puerto $puerto abierto solo en redes PRIVADAS y solo para equipos de la misma red." "Done: port $puerto open on PRIVATE networks only, and only for devices on the same network.") -ForegroundColor Green

# La red Wi-Fi de la casa tiene que estar marcada como «Privada»; si está como «Pública», el celular no entra.
Write-Host ''
Write-Host (T 'Tus redes ahora:' 'Your networks now:')
Get-NetConnectionProfile | ForEach-Object {
  $tipo = if ($_.NetworkCategory -eq 'Private') { T 'Privada (bien)' 'Private (good)' } elseif ($_.NetworkCategory -eq 'Public') { T 'PÚBLICA: el Puente no se ve desde aquí' 'PUBLIC: Puente is not reachable on this network' } else { $_.NetworkCategory }
  Write-Host ("  {0}  ->  {1}" -f $_.Name, $tipo)
}
