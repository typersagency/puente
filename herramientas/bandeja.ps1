# Puente by Typers junto al reloj de Windows (MIT): enciende el Puente sin ventana negra,
# avisa cuando llegan fotos o videos y se apaga desde su menú (clic derecho en el ícono).
# La primera vez pregunta qué carpeta compartir. Español o inglés según el idioma de Windows.
# Se abre con herramientas\encender.pyw (acceso directo del escritorio y de inicio de Windows).
# Uso a mano: powershell -STA -ExecutionPolicy Bypass -File herramientas\bandeja.ps1 [-Mostrar]
param([switch]$Mostrar)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$raiz = Split-Path -Parent $PSScriptRoot

$es = (Get-UICulture).TwoLetterISOLanguageName -eq 'es'
function T($textoEs, $textoEn) { if ($es) { $textoEs } else { $textoEn } }

# Configuración: config.json + lo de este equipo (config.local.json gana).
$cfg = Get-Content (Join-Path $raiz 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$puerto = $cfg.puerto
$raizCompartida = $cfg.carpetas.raiz
$https = [bool]$cfg.https.cert
$rutaLocal = Join-Path $raiz 'config.local.json'
$local = $null
if (Test-Path $rutaLocal) {
  $local = Get-Content $rutaLocal -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($local.puerto) { $puerto = $local.puerto }
  if ($local.carpetas.raiz) { $raizCompartida = $local.carpetas.raiz }
  if ($local.https.cert) { $https = $true }
}
if ($raizCompartida -like '~*') { $raizCompartida = $HOME + $raizCompartida.Substring(1) }
$pc = $(if ($https) { "https://localhost:$puerto/pc" } else { "http://127.0.0.1:$puerto/pc" })

# Un solo Puente a la vez: si ya está encendido, solo muestra la pantalla del QR.
$unico = New-Object System.Threading.Mutex($false, 'Local\PuenteByTypersBandeja')
if (-not $unico.WaitOne(0)) { Start-Process $pc; exit }

# La primera vez: ¿qué carpeta compartir con el celular? (se guarda en config.local.json)
if (-not $raizCompartida) {
  $dialogo = New-Object System.Windows.Forms.FolderBrowserDialog
  $dialogo.Description = T 'Puente by Typers: elige la carpeta que quieres compartir con tu celular (por ejemplo, la de tus proyectos). Desde el celular podrás elegir cualquier carpeta dentro de ella.' `
                           'Puente by Typers: choose the folder to share with your phone (for example, your projects folder). From your phone you can pick any folder inside it.'
  $dialogo.SelectedPath = [Environment]::GetFolderPath('MyPictures')
  if ($dialogo.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
    [System.Windows.Forms.MessageBox]::Show((T 'No elegiste carpeta, así que el Puente no se encendió. Ábrelo de nuevo cuando quieras (ícono «Puente» del escritorio).' `
                                               'No folder was chosen, so Puente did not start. Open it again whenever you want (the «Puente» icon on your desktop).'), 'Puente by Typers') | Out-Null
    exit
  }
  $raizCompartida = $dialogo.SelectedPath
  if (-not $local) { $local = [pscustomobject]@{} }
  if (-not $local.carpetas) { $local | Add-Member -NotePropertyName carpetas -NotePropertyValue ([pscustomobject]@{}) -Force }
  $local.carpetas | Add-Member -NotePropertyName raiz -NotePropertyValue $raizCompartida -Force
  [IO.File]::WriteAllText($rutaLocal, ($local | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding $false))   # sin BOM
}

$icono = New-Object System.Windows.Forms.NotifyIcon
$icono.Icon = New-Object System.Drawing.Icon (Join-Path $PSScriptRoot 'puente.ico')
$icono.Text = 'Puente by Typers'
$icono.Visible = $true

function Terminar {
  $script:reloj.Stop()
  if ($script:proc -and -not $script:proc.HasExited) { Stop-Process -Id $script:proc.Id -Force -ErrorAction SilentlyContinue }
  $icono.Visible = $false
  $icono.Dispose()
  [System.Windows.Forms.Application]::Exit()
}

# Encender el Puente (pythonw: sin ventana). Los errores quedan en datos\registro\errores.txt.
$registro = Join-Path $raiz 'datos\registro'
New-Item -ItemType Directory -Force $registro | Out-Null
$errores = Join-Path $registro 'errores.txt'
$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
  [System.Windows.Forms.MessageBox]::Show((T 'No encuentro Python (pythonw.exe). Instálalo desde python.org y vuelve a abrir el Puente.' `
                                             'Python (pythonw.exe) was not found. Install it from python.org and open Puente again.'), 'Puente by Typers') | Out-Null
  $icono.Dispose(); exit 1
}
$script:proc = Start-Process $pythonw -ArgumentList "`"$raiz\puente.py`"", '--sin-navegador' -WorkingDirectory $raiz -PassThru -RedirectStandardError $errores

# Menú del ícono
$menu = New-Object System.Windows.Forms.ContextMenuStrip
[void]$menu.Items.Add((T 'Mostrar QR, PIN y llave' 'Show QR, PIN and key'), $null, { Start-Process $pc })
$script:fijos = $menu.Items.Count
[void]$menu.Items.Add('-')
[void]$menu.Items.Add((T 'Apagar el Puente' 'Stop Puente'), $null, { Terminar })
# Las últimas carpetas usadas (datos\destino.json), al día cada vez que se abre el menú.
$menu.add_Opening({
  while ($menu.Items.Count -gt $script:fijos + 2) { $menu.Items.RemoveAt($script:fijos) }
  $archivo = Join-Path $raiz 'datos\destino.json'
  if (-not (Test-Path $archivo)) { return }
  try { $d = Get-Content $archivo -Raw -Encoding UTF8 | ConvertFrom-Json } catch { return }
  $i = $script:fijos
  foreach ($rel in @($d.recientes)) {
    if (-not $rel) { continue }
    $carpeta = [IO.Path]::GetFullPath((Join-Path $raizCompartida $rel))
    $item = New-Object System.Windows.Forms.ToolStripMenuItem ((T 'Abrir ' 'Open ') + ($rel -replace '/', ' › '))
    $item.add_Click({ Start-Process explorer.exe "`"$carpeta`"" }.GetNewClosure())
    $menu.Items.Insert($i, $item); $i++
  }
})
$icono.ContextMenuStrip = $menu
$icono.add_MouseClick({ if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) { Start-Process $pc } })

# Avisos: lee lo nuevo del registro y junta lo que llega seguido en un solo aviso.
$log = Join-Path $registro 'subidas.log'
$script:leido = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
$script:pendientes = New-Object System.Collections.ArrayList
$script:ultimo = [datetime]::MinValue
$script:abrir = $null
$script:encendido = $false

function Avisar {
  $n = $script:pendientes.Count
  $ev = $script:pendientes[$n - 1]
  $videos = @($script:pendientes | Where-Object { $_.tipo -in 'mov', 'mp4' }).Count
  $fotos = $n - $videos
  $partes = @()
  if ($fotos) { $partes += $(if ($fotos -eq 1) { T '1 foto' '1 photo' } else { "$fotos " + (T 'fotos' 'photos') }) }
  if ($videos) { $partes += $(if ($videos -eq 1) { '1 video' } else { "$videos videos" }) }
  $titulo = $(if ($n -eq 1) { T 'Llegó ' 'Received ' } else { T 'Llegaron ' 'Received ' }) + ($partes -join (T ' y ' ' and '))
  $archivo = if ($ev.jpg) { $ev.jpg } else { $ev.guardado }
  $donde = $ev.destino -replace '/', ' › '
  $script:abrir = if ($ev.carpeta) { Join-Path $ev.carpeta $archivo } else { $null }
  $icono.ShowBalloonTip(6000, $titulo, "$donde`n" + (T 'Clic para abrir la carpeta.' 'Click to open the folder.'), [System.Windows.Forms.ToolTipIcon]::Info)
  $script:pendientes.Clear()
}
$icono.add_BalloonTipClicked({
  if ($script:abrir -and (Test-Path $script:abrir)) { Start-Process explorer.exe "/select,`"$script:abrir`"" }
  elseif ($script:abrir) { Start-Process explorer.exe "`"$(Split-Path $script:abrir)`"" }
})

function LeerRegistro {
  if (-not (Test-Path $log)) { return }
  $largo = (Get-Item $log).Length
  if ($largo -lt $script:leido) { $script:leido = 0 }
  if ($largo -eq $script:leido) { return }
  $fs = [IO.File]::Open($log, 'Open', 'Read', 'ReadWrite')
  try {
    [void]$fs.Seek($script:leido, 'Begin')
    $buf = New-Object byte[] ($largo - $script:leido)
    $leidos = $fs.Read($buf, 0, $buf.Length)
  } finally { $fs.Close() }
  $fin = [Array]::LastIndexOf($buf, [byte]10, $leidos - 1)   # solo líneas completas
  if ($fin -lt 0) { return }
  $script:leido += $fin + 1
  foreach ($linea in [Text.Encoding]::UTF8.GetString($buf, 0, $fin + 1) -split "`n") {
    if (-not $linea.Trim()) { continue }
    try { $ev = $linea | ConvertFrom-Json } catch { continue }
    if ($ev.evento -eq 'subida') { [void]$script:pendientes.Add($ev); $script:ultimo = Get-Date }
    elseif ($ev.evento -eq 'encendido' -and -not $script:encendido) {
      $script:encendido = $true
      $icono.Text = 'Puente by Typers · ' + (T 'encendido' 'running')
      if ($Mostrar) { Start-Process $pc }
    }
  }
}

$script:reloj = New-Object System.Windows.Forms.Timer
$script:reloj.Interval = 1500
$script:reloj.add_Tick({
  try {
    if ($script:proc.HasExited) {
      $script:reloj.Stop()
      $detalle = if (Test-Path $errores) { ((Get-Content $errores -Encoding UTF8 -Tail 1) -join '') } else { '' }
      [System.Windows.Forms.MessageBox]::Show((T 'El Puente se apagó.' 'Puente stopped.') + "`n`n$detalle", 'Puente by Typers') | Out-Null
      Terminar
      return
    }
    LeerRegistro
    if ($script:pendientes.Count -and ((Get-Date) - $script:ultimo).TotalSeconds -ge 3) { Avisar }
  } catch { }
})
$script:reloj.Start()
[System.Windows.Forms.Application]::Run()
