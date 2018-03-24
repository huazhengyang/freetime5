# -*- coding=utf-8
'''
Created on 2016年9月23日

@author: zhaol
'''
from majiang2.table_state.state import MTableState
from freetime5.util import ftlog

class MDaFengRuleBase(object):
    """
    是否可以刮大风
    
    先决条件是
    1）用户已经听牌
    2）玩法允许刮大风胡牌
    """
    
    def __init__(self):
        super(MDaFengRuleBase, self).__init__()
    
    @classmethod    
    def canWinByDaFeng(self, player, tiles, tile, gangRuleMgr, winRuleMgr, tableTileMgr):
        gangs = gangRuleMgr.hasGang(tiles, tile, MTableState.TABLE_STATE_NEXT, {"seatId":player.curSeatId})
        ftlog.debug('MDaFengRuleBase.canWinByDaFeng check GUA_DA_FENG tiles:', tiles
                     , ' gangs:', gangs
                     , ' tile:', tile)
        #摸到自己的碰牌和手里的刻牌(可杠)
        for gang in gangs:
            if tile not in gang['pattern']:
                continue
            
            if player.canGang(gang
                          , True
                          , tiles
                          , tile
                          , winRuleMgr
                          , tableTileMgr.getMagicTiles(player.isTing())):
                return True
        
        return False