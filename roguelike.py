# import libcodpy as tcod # looks deprecated
import tcod

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

font_path = 'arial10x10.png'  # unnecessary? this will look in the same folder as this script
# font_path = 'tcod.data.fonts.arial10x10.png' # should really have libtcod full path here ('libtcod/libtcod/data/fonts/arial10x10.png')
font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD  # the layout may need to change with a different font file
tcod.console_set_custom_font(font_path, font_flags)

window_title = 'Python 3 libtcod tutorial'
fullscreen = False
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, window_title, fullscreen)

# Want turnbased? Comment this line
tcod.sys_set_fps(LIMIT_FPS)


# main loop
while not tcod.console_is_window_closed():

    # '0' is which console we're printing to - here, that's the screen
    tcod.console_set_default_foreground(0, tcod.white)

    # print character
    tcod.console_put_char(0, 1, 1, '@', tcod.BKGND_NONE)

    # flush changes to screen
    tcod.console_flush()