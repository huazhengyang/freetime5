# -*- coding=utf-8
'''
Created on 2016年9月23日
听牌规则
@author: zhaol
'''
from majiang2.ai.ting import MTing
from majiang2.ting_rule.ting_rule import MTingRule
from majiang2.table_tile.table_tile import MTableTile

class MTingJiNanRule(MTingRule):
    """胡牌规则
    """
    def __init__(self):
        super(MTingJiNanRule, self).__init__()
    
    def canTing(self, tiles, leftTiles, tile, magicTiles = [], winSeatId = 0):
        """子类必须实现
        参数：
        1）tiles 该玩家的手牌
        
        返回值：
        是否可以听牌，听牌详情
        """
        return MTing.canTing(self.tilePatternChecker, self.tableTileMgr, tiles, leftTiles, self.winRuleMgr, tile, magicTiles, winSeatId)

    def canTingBeforeAddTile(self, tiles, leftTiles, magicTiles=[], winSeatId=0):
        """子类必须实现
        参数：
        1）tiles 该玩家的手牌

        返回值：
        是否可以听牌，听牌详情
        """
        return MTing.canTingBeforeAddTile(self.tilePatternChecker, self.tableTileMgr, tiles, leftTiles, self.winRuleMgr, magicTiles, winSeatId)

    def canTingAfterPeng(self, tiles):
        """"碰之后是否可以马上听牌"""
        # 和抢听是矛盾的，非抢听情况下，卡五星玩家正常碰牌后，应马上弹出听牌按钮
        return True

    def getTingLiangMode(self):
        '''听牌时显示要胡的牌'''
        return MTableTile.MODE_LIANG_HAND