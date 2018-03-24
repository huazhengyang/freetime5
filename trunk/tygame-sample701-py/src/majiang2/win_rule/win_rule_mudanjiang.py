# -*- coding=utf-8
'''
Created on 2016年9月23日
庄家规则
@author: zhaol
'''
from majiang2.win_rule.win_rule import MWinRule
from majiang2.ai.win import MWin
from majiang2.player.hand.hand import MHand
from freetime5.util import ftlog
from majiang2.tile.tile import MTile

class MWinRuleMudanjiang(MWinRule):
    """
    牡丹江玩法的和牌规则
    2）没听牌 不和
    不能平胡和对倒
    3）不能手把一。即：不能吃碰后只剩余一张牌，即最后最少要有4张牌才可上听。（限制剩4个牌后，不可以吃碰杠操作）
    4）截和，不能一炮双响。如果同时存在2个玩家和牌，按照逆时针方向顺序在前者有优先牌权。
    """
    def __init__(self):
        super(MWinRuleMudanjiang, self).__init__()
    
    def isHu(self, tiles, tile, isTing, getTileType, magicTiles = [], tingNodes = [], winSeatId = 0):
        if not isTing:
            # 没听牌 不和
            return False, []
        
        
        # 哈尔滨打宝炮(先不支持 之后通过配置项目支持) 玩家上听后没有听牌的玩家打出宝牌 则听牌玩家和牌
        # 听牌之后自摸到宝牌 自动和牌
        if isTing and getTileType == MWinRule.WIN_BY_MYSELF:
            if (tile in magicTiles):
                # 听牌并且是宝牌，和牌
                return True, []
        
        result, pattern = MWin.isHu(tiles[MHand.TYPE_HAND])
        if not result:
            return False, []
        
        #从tingNode中判断，如果是听规则中的才算胡
        if len(tingNodes) > 0:
            hasTile = False
            pattern = []
            #[{'winTile': 16, 'winTileCount': 0, 'pattern': [[16, 17, 18], [12, 12]]}, {'winTile': 19, 'winTileCount': 0, 'pattern': [[17, 18, 19], [12, 12]]}] 
            for tingNode in tingNodes:
                if tingNode['winTile'] == tile:
                    hasTile = True
                    pattern = tingNode['pattern']
                    break
            if hasTile:
                return True, pattern
            else:
                return False, []
        
        return True, pattern
    
    def isMagicAfertTingHu(self, isTing, winNodes, magicTiles, extendInfo = {}):
        if len(magicTiles) == 0:
            #ftlog.debug('isMagicAfertTingHu magcicTile is zero')
            return False
        magicTile = magicTiles[0]
        # 宝牌是红中，直接胡
        if magicTile == MTile.TILE_HONG_ZHONG and extendInfo.get('hongZhong', 0):
            return True
        
        if isTing:
            #[{'winTile': 1, 'winTileCount': 3, 'pattern': [[6, 6], [5, 6, 7], [4, 5, 6], [1, 2, 3]]}
            for winNode in winNodes:
                if winNode['winTile'] == magicTile:
                    ftlog.debug('isMagicAfertTingHu success magcicTile is', magicTile)
                    return True
        return False
    
    def canWinAfterChiPengGang(self, tiles):
        """吃完之后是否能和牌"""
        handTiles = tiles[MHand.TYPE_HAND]
        count = len(handTiles) - 2
        if count < 4:
            return False
        
        return True
    
if __name__ == "__main__":
    tiles = [[1,2,3,4,5,6,7,8,9,11,11], [[12,13,14]], [], [], [], []]
    rule = MWinRuleMudanjiang()
    ftlog.debug(rule.isHu(tiles, 2, True, [3]))