import sys
import xbmc
import xbmcgui

DEFAULT_SKIN = "skin.estuary"

def main():
    skin_id = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else DEFAULT_SKIN
    xbmc.log("skin.dejavu: switching skin to {}".format(skin_id), xbmc.LOGINFO)
    xbmcgui.Dialog().notification("dejaVu", "Retour vers {}".format(skin_id), xbmcgui.NOTIFICATION_INFO, 1000)
    xbmc.executebuiltin("LoadSkin({})".format(skin_id))

if __name__ == "__main__":
    main()
