PROCESS_HINTS = {
    # --- Browsers ---
    "Google.Chrome": ["chrome.exe"],
    "Google.Chrome.Beta": ["chrome.exe"],
    "Google.Chrome.Dev": ["chrome.exe"],
    "Google.Chrome.Canary": ["chrome.exe"],
    "Mozilla.Firefox": ["firefox.exe"],
    "Mozilla.Firefox.ESR": ["firefox.exe"],
    "Mozilla.Firefox.DeveloperEdition": ["firefox.exe"],
    "Mozilla.Firefox.Nightly": ["firefox.exe"],
    "Brave.Brave": ["brave.exe"],
    "Microsoft.Edge": ["msedge.exe"],
    "Microsoft.Edge.Beta": ["msedge.exe"],
    "Microsoft.Edge.Dev": ["msedge.exe"],
    "Vivaldi.Vivaldi": ["vivaldi.exe"],
    "Opera.Opera": ["opera.exe", "launcher.exe"],
    "Opera.OperaGX": ["opera.exe", "launcher.exe"],
    "TheBrowserCompany.Arc": ["Arc.exe"],
    "TorProject.TorBrowser": ["firefox.exe", "tor.exe"],

    # --- Code editors / IDEs ---
    "Microsoft.VisualStudioCode": ["Code.exe"],
    "Microsoft.VisualStudioCode.Insiders": ["Code - Insiders.exe"],
    "Microsoft.VisualStudio.2022.Community": ["devenv.exe"],
    "Microsoft.VisualStudio.2022.Professional": ["devenv.exe"],
    "Microsoft.VisualStudio.2022.Enterprise": ["devenv.exe"],
    "Microsoft.VisualStudio.2022.BuildTools": ["devenv.exe"],
    "JetBrains.IntelliJIDEA.Community": ["idea64.exe"],
    "JetBrains.IntelliJIDEA.Ultimate": ["idea64.exe"],
    "JetBrains.PyCharm.Community": ["pycharm64.exe"],
    "JetBrains.PyCharm.Professional": ["pycharm64.exe"],
    "JetBrains.WebStorm": ["webstorm64.exe"],
    "JetBrains.PhpStorm": ["phpstorm64.exe"],
    "JetBrains.CLion": ["clion64.exe"],
    "JetBrains.Rider": ["rider64.exe"],
    "JetBrains.GoLand": ["goland64.exe"],
    "JetBrains.RubyMine": ["rubymine64.exe"],
    "JetBrains.DataGrip": ["datagrip64.exe"],
    "JetBrains.Fleet": ["Fleet.exe"],
    "JetBrains.Toolbox": ["jetbrains-toolbox.exe"],
    "Google.AndroidStudio": ["studio64.exe"],
    "SublimeHQ.SublimeText.4": ["sublime_text.exe"],
    "Anysphere.Cursor": ["Cursor.exe"],
    "Notepad++.Notepad++": ["notepad++.exe"],
    "UnityTechnologies.UnityHub": ["Unity Hub.exe"],

    # --- Dev tools ---
    "Git.Git": ["git.exe", "bash.exe"],
    "GitHub.GitHubDesktop": ["GitHubDesktop.exe"],
    "Axosoft.GitKraken": ["gitkraken.exe"],
    "Docker.DockerDesktop": ["Docker Desktop.exe", "com.docker.backend.exe"],
    "OpenJS.NodeJS": ["node.exe"],
    "OpenJS.NodeJS.LTS": ["node.exe"],
    "Postman.Postman": ["Postman.exe"],
    "Insomnia.Insomnia": ["Insomnia.exe"],

    # --- Terminals / shells ---
    "Microsoft.WindowsTerminal": ["WindowsTerminal.exe"],
    "Alacritty.Alacritty": ["alacritty.exe"],
    "wez.wezterm": ["wezterm.exe", "wezterm-gui.exe"],
    "Eugeny.Tabby": ["Tabby.exe"],
    "Maximus5.ConEmu": ["ConEmu64.exe", "ConEmu.exe"],
    "JanDeDobbeleer.OhMyPosh": ["oh-my-posh.exe"],

    # --- Communication ---
    "Discord.Discord": ["Discord.exe"],
    "Discord.Discord.PTB": ["DiscordPTB.exe"],
    "Discord.Discord.Canary": ["DiscordCanary.exe"],
    "SlackTechnologies.Slack": ["slack.exe"],
    "Microsoft.Teams": ["ms-teams.exe", "Teams.exe"],
    "Zoom.Zoom": ["Zoom.exe"],
    "Telegram.TelegramDesktop": ["Telegram.exe"],
    "OpenWhisperSystems.Signal": ["Signal.exe"],
    "Element.Element": ["Element.exe"],
    "Mozilla.Thunderbird": ["thunderbird.exe"],
    "Mozilla.Thunderbird.ESR": ["thunderbird.exe"],
    "Mozilla.Thunderbird.ESR.es-ES": ["thunderbird.exe"],

    # --- Cloud storage / sync ---
    "Dropbox.Dropbox": ["Dropbox.exe"],
    "Google.GoogleDrive": ["GoogleDriveFS.exe"],
    "Microsoft.OneDrive": ["OneDrive.exe"],
    "Nextcloud.NextcloudDesktop": ["nextcloud.exe"],
    "MEGA.MEGASync": ["MEGAsync.exe"],
    "Syncthing.Syncthing": ["syncthing.exe"],

    # --- Gaming launchers ---
    "Valve.Steam": ["steam.exe"],
    "EpicGames.EpicGamesLauncher": ["EpicGamesLauncher.exe"],
    "ElectronicArts.EADesktop": ["EADesktop.exe"],
    "Ubisoft.Connect": ["upc.exe", "UbisoftConnect.exe"],
    "Blizzard.BattleNet": ["Battle.net.exe"],
    "GOG.Galaxy": ["GalaxyClient.exe"],
    "JosefNemec.Playnite": ["Playnite.DesktopApp.exe"],

    # --- Peripherals / RGB ---
    "Logitech.GHUB": ["lghub.exe", "lghub_agent.exe", "lghub_updater.exe"],
    "Logitech.OptionsPlus": ["logioptionsplus.exe"],
    "Razer.Synapse": ["Razer Synapse.exe"],
    "Corsair.iCUE": ["iCUE.exe"],
    "SteelSeries.GG": ["SteelSeriesGG.exe"],
    "CalcProgrammer1.OpenRGB": ["OpenRGB.exe"],
    "WhirlwindFX.SignalRgb": ["SignalRgb.exe"],
    "Elgato.StreamDeck": ["StreamDeck.exe"],

    # --- Media players ---
    "VideoLAN.VLC": ["vlc.exe"],
    "clsid2.mpc-hc": ["mpc-hc64.exe", "mpc-hc.exe"],
    "shinchiro.mpv": ["mpv.exe"],
    "PeterPawlowski.foobar2000": ["foobar2000.exe"],
    "AIMP.AIMP": ["AIMP.exe"],
    "Apple.iTunes": ["iTunes.exe"],
    "Spotify.Spotify": ["Spotify.exe"],

    # --- Media creation ---
    "OBSProject.OBSStudio": ["obs64.exe", "obs32.exe"],
    "Streamlabs.Streamlabs": ["Streamlabs OBS.exe"],
    "Audacity.Audacity": ["Audacity.exe"],
    "HandBrake.HandBrake": ["HandBrake.exe"],
    "KDE.Kdenlive": ["kdenlive.exe"],
    "Cockos.REAPER": ["reaper.exe"],

    # --- Graphics / 3D ---
    "GIMP.GIMP": ["gimp-2.10.exe"],
    "Inkscape.Inkscape": ["inkscape.exe"],
    "BlenderFoundation.Blender": ["blender.exe"],
    "KDE.Krita": ["krita.exe"],
    "dotPDN.PaintDotNet": ["paintdotnet.exe", "PaintDotNet.exe"],
    "IrfanSkiljan.IrfanView": ["i_view64.exe", "i_view32.exe"],
    "XnSoft.XnViewMP": ["xnviewmp.exe"],
    "JGraph.Drawio": ["draw.io.exe"],
    "Ultimaker.Cura": ["UltiMaker-Cura.exe", "Cura.exe"],

    # --- Screenshot / capture ---
    "ShareX.ShareX": ["ShareX.exe"],
    "Greenshot.Greenshot": ["Greenshot.exe"],
    "Skillbrains.Lightshot": ["Lightshot.exe"],

    # --- Productivity / notes ---
    "Obsidian.Obsidian": ["Obsidian.exe"],
    "Notion.Notion": ["Notion.exe"],
    "Evernote.Evernote": ["Evernote.exe"],
    "JoplinApp.Joplin": ["Joplin.exe"],
    "Typora.Typora": ["Typora.exe"],
    "DigitalScholar.Zotero": ["zotero.exe"],
    "calibre.calibre": ["calibre.exe"],
    "Microsoft.PowerToys": ["PowerToys.exe"],

    # --- Office ---
    "TheDocumentFoundation.LibreOffice": ["soffice.bin", "soffice.exe"],
    "ONLYOFFICE.DesktopEditors": ["DesktopEditors.exe"],

    # --- PDF ---
    "Adobe.Acrobat.Reader.64-bit": ["AcroRd32.exe", "Acrobat.exe"],
    "Adobe.Acrobat.Reader.32-bit": ["AcroRd32.exe"],
    "SumatraPDF.SumatraPDF": ["SumatraPDF.exe"],
    "Foxit.FoxitReader": ["FoxitReader.exe"],

    # --- Archivers ---
    "7zip.7zip": ["7zFM.exe", "7zG.exe"],
    "WinRAR.WinRAR": ["WinRAR.exe"],
    "Giorgiotani.Peazip": ["peazip.exe"],
    "Bandisoft.Bandizip": ["Bandizip.exe"],

    # --- Password managers ---
    "Bitwarden.Bitwarden": ["Bitwarden.exe"],
    "AgileBits.1Password": ["1Password.exe"],
    "DominikReichl.KeePass": ["KeePass.exe"],
    "KeePassXCTeam.KeePassXC": ["KeePassXC.exe"],

    # --- Remote / networking ---
    "TeamViewer.TeamViewer": ["TeamViewer.exe"],
    "AnyDeskSoftwareGmbH.AnyDesk": ["AnyDesk.exe"],
    "Parsec.Parsec": ["parsecd.exe"],
    "RustDesk.RustDesk": ["rustdesk.exe"],
    "PuTTY.PuTTY": ["putty.exe"],
    "WinSCP.WinSCP": ["WinSCP.exe"],
    "TimKosse.FileZilla.Client": ["filezilla.exe"],
    "WiresharkFoundation.Wireshark": ["Wireshark.exe"],

    # --- Database tools ---
    "DBeaver.DBeaver.Community": ["dbeaver.exe"],
    "DBeaver.DBeaver": ["dbeaver.exe"],
    "Oracle.MySQLWorkbench": ["MySQLWorkbench.exe"],
    "PostgreSQL.pgAdmin": ["pgAdmin4.exe"],
    "MongoDB.Compass.Community": ["MongoDBCompass.exe"],
    "MongoDB.Compass.Full": ["MongoDBCompass.exe"],
    "HeidiSQL.HeidiSQL": ["heidisql.exe"],

    # --- Virtualization ---
    "Oracle.VirtualBox": ["VirtualBox.exe", "VirtualBoxVM.exe"],
    "VMware.WorkstationPro": ["vmware.exe"],

    # --- Torrent ---
    "qBittorrent.qBittorrent": ["qbittorrent.exe"],
    "Transmission.Transmission": ["transmission-qt.exe"],
    "DelugeTeam.Deluge": ["deluge.exe"],

    # --- System / hardware monitors ---
    "REALiX.HWiNFO": ["HWiNFO64.exe", "HWiNFO32.exe"],
    "CPUID.CPU-Z": ["cpuz.exe"],
    "TechPowerUp.GPU-Z": ["GPU-Z.exe"],
    "CPUID.HWMonitor": ["HWMonitor.exe"],
    "CrystalDewWorld.CrystalDiskInfo": ["DiskInfo64.exe", "DiskInfo32.exe"],
    "CrystalDewWorld.CrystalDiskMark": ["DiskMark64.exe", "DiskMark32.exe"],
    "Guru3D.Afterburner": ["MSIAfterburner.exe"],
    "AutoHotkey.AutoHotkey": ["AutoHotkey.exe", "AutoHotkey64.exe", "AutoHotkeyU64.exe"],
}
