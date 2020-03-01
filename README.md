# Roguelike

**(A Dungeon Crawler Game)**

![Spooky Skeletons](skeletonDance.gif)


For Python3 Venv install:
```
python3 -m venv venv    # creates folder “venv” for virtual env
. venv/bin/activate     # hop into env
pip install -r requirements.txt
```

Following this guide:
http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python3%2Blibtcod

12/16/2019 - Starting "Using Items" (inventory works, can't use the items themselves yet)
http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python3%2Blibtcod,_part_8

(I've skipped Save and Load, can't download SHELVE, so can't test it rn. Dungeon_level needs including (from next step) in saving/loading module too)

STOPPED: Testing random choice function in monster, item population. About to start: "Monster and item progression"

http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python3%2Blibtcod,_part_12

Next steps google doc: https://docs.google.com/document/d/1aqwiX_d9JmYfrtmHeO3DMiPN1PLNOPN_K3d74eDKfkU/edit


Next up:

- animations with multiple frames (missles, in ranged_attack specifically)
- fireball and such as multi-frame animations
- Abilities and abilities menu

(Line 319 - doesn't show animation correctly. The bolt doesnt...go the right way, doesn't get drawn)
