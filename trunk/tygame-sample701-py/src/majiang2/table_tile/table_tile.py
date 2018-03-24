# -*- coding=utf-8
'''
Created on 2016年9月23日
牌桌麻将牌的管理器
包括：
1）发牌
2）牌桌上的出牌
3）宝牌

发牌说明：
发牌涉及到好牌点
@author: zhaol
'''
from freetime5.util import ftlog
from majiang2.dealer.dealer_factory import DealerFactory
from majiang2.table_tile.test.table_tile_test_factory import MTableTileTestFactory
from majiang2.tile.tile import MTile
import copy


class MTableTile(object):

    # 不亮牌
    MODE_LIANG_NONE = 0
    # 亮牌，亮全部手牌
    MODE_LIANG_HAND = 1
    # 亮牌，只亮听口牌
    MODE_LIANG_TING = 2
    # 听牌，仅能用于客户端提示
    MODE_LIANG_TING_TIPS = 3
    # 亮胡的牌
    MODE_LIANG_WIN_TILES = 4

    '''
    听牌胡牌后，杠的相关开关
    '''
    # 听牌／胡牌后不可杠
    AFTER_TING_HU_NONE = 0b1
    
    # 听牌／胡牌后可杠不影响听口的牌
    AFTER_TING_HU_NO_CHANGE_TING = 0b10
    
    # 听牌 只能杠扣下的牌
    AFTER_TING_HU_KOU = 0b100
    
    # 听牌／胡牌 不可以暗杠
    AFTER_TING_HU_WITHOUT_ANGANG = 0b1000
    
    # 听牌／胡牌 不可以明杠
    AFTER_TING_HU_WITHOUT_MINGGANG = 0b10000
    
    # 听牌／胡牌 只能蓄杠 蓄杠肯定不影响听口牌
    AFTER_TING_HU_XUGANG = 0b100000
    
    # 抢杠规则 暗杠
    QIANG_GANG_RULE_AN = 0b001
    # 抢杠规则 补杠，又称 回头杠
    QIANG_GANG_RULE_HUI_TOU = 0b010
    # 抢杠规则 杠别人打出的牌 明杠
    QIANG_GANG_RULE_OTHER = 0b100

    def __init__(self, playerCount, playMode, runMode):
        super(MTableTile, self).__init__()
        self.__player_count = playerCount
        self.__play_mode = playMode
        self.__run_mode = runMode
        # 本局剩余的牌
        self.__tiles = []
        # 每个玩家出过的牌
        self.__drop_tiles = [[] for _ in range(self.playCount)]
        # 每个玩家摸到的牌
        self.__add_tiles = [[] for _ in range(self.playCount)]
        # 每个玩家门前的牌
        self.__men_tiles = [[] for _ in range(self.playCount)]
        # 每个玩家摸到的花牌
        self.__flower_tiles = [[] for _ in range(self.playCount)]
        # 每个玩家累积的花分
        self.__flower_scores = [0 for _ in range(self.playCount)]
        # 特殊用途的牌，比如宝牌，被选出后，不用于打牌
        self.__special_tiles = []
        # 发牌器
        self.__dealer = DealerFactory.getDealer(self.__play_mode, playerCount)
        # 摆牌器
        self.__tile_test_mgr = MTableTileTestFactory.getTableTileTestMgr(playerCount, playMode, runMode)
        # 玩家
        self.__players = None
        # 牌桌配置，方便自定义行为的操作
        self.__table_config = {}
        # 杠可以用的赖子数
        self.__magics_gang_max_count = 4
        # 允许抢杠胡的类型用二进制表示,这个变量只在判断了抢杠胡状态下使用，默认允许回头杠可以被抢杠胡
        self.__qiang_gang_rule = self.QIANG_GANG_RULE_HUI_TOU
        # 本局杠的数量
        self.__gang_count = 0
        # 调整发牌，去掉风牌
        self.__remove_feng = False
        self.__remove_arrow = False
        # 听牌的先后顺序
        self.__ting_index = []
        # 海底捞的数值
        self.__haidilao_count = 4
        # 定的缺
        self.__absence_colors = [-1 for _ in range(self.playCount)]
        # 马牌
        self.__horse_tiles = []
        # 一炮多响会影响听牌预览的算牌结果，要去掉多算的牌
        self.__multiTileNum = {}
        # 玩家手牌的排序变化 默认为万筒条
        self.__hand_tile_color_sort = [[] for _ in range(self.playCount)]
    
    def reset(self):
        """重置"""
        self.__tiles = []
        self.__drop_tiles = [[] for _ in range(self.__player_count)]
        self.__add_tiles = [[] for _ in range(self.playCount)]
        self.__men_tiles = [[] for _ in range(self.playCount)]
        self.__special_tiles = []
        self.__dealer.reset()
        self.__tile_test_mgr = MTableTileTestFactory.getTableTileTestMgr(self.playCount, self.playMode, self.runMode)
        self.__players = None
        self.__gang_count = 0
        self.__flower_tiles = [[] for _ in range(self.playCount)]
        self.__flower_scores = [0 for _ in range(self.playCount)]
        self.__remove_arrow = False
        self.__remove_feng = False
        self.__ting_index = []
        self.__horse_tiles = []
        self.__genTile = 0
        self.__multiTileNum = {}
        self.__hand_tile_color_sort = [[] for _ in range(self.playCount)]

    @property
    def handTileColorSort(self):
        return self.__hand_tile_color_sort
    
    def setHandTileColorSort(self, colorList):
        self.__hand_tile_color_sort = colorList
    
    def sortHandTileColor(self, players, isAbsence):
        '''
        玩家手牌花色排序计算，保存到__hand_tile_sort，相应玩法各自实现
        '''
        pass

    @property
    def multiTileNum(self):
        return self.__multiTileNum
    
    def setMultiTileNum(self, tile, numTile):
        '''
        设置一炮多响多算的牌
        :param tile:赢的牌
        :param numTile:多的数目
        '''
        if tile in self.__multiTileNum:
            self.__multiTileNum[tile] += numTile
        else:
            self.__multiTileNum[tile] = numTile
        

    @property
    def absenceColors(self):
        return self.__absence_colors

    def setAbsenceColors(self, absenceColors):
        self.__absence_colors = absenceColors
        ftlog.debug('table_tile absenceColors:', self.__absence_colors, 'absenceColors:', absenceColors)
        
    @property
    def isAbsenceFinish(self):
        return True
    '''
    关于海底捞/只抓不打
    对于摸牌的人，都是只判断自摸，不判断杠牌等。
    海底捞的时候：
    1）有的玩法允许打牌，此时打出去的牌不能点炮
    2）有的玩法不允许打牌，此时海底牌留在手里
    修改，去掉getTilesNoDropCount，获取海底捞时，是否可以打出牌
    '''

    @property
    def haidilaoCount(self):
        return self.__haidilao_count
    
    def setHaidilaoCount(self, count):
        self.__haidilao_count = count
        
    def canDropWhenHaidiLao(self):
        '''
        海底捞时是否可以出牌
            True 可以打出牌
            False 不可以打出牌
        '''
        return True    
        
    def isHaidilao(self):
        ftlog.debug('MTableTile.isHaidilao self.getTilesLeftCount():', self.getTilesLeftCount()
                    , ' self.getFlowCount():', self.getFlowCount()
                    , ' self.haidilaoCount:', self.haidilaoCount)
        return (self.getTilesLeftCount() - self.getFlowCount()) < self.haidilaoCount
                
    @property
    def tingIndex(self):
        return self.__ting_index
    
    def setTingIndex(self, tingIndex):
        self.__ting_index = tingIndex
        
    def appendTingIndex(self, index):
        self.__ting_index.append(index)
        
    @property
    def removeFeng(self):
        return self.__remove_feng
    
    def setRemoveFeng(self, removeFeng):
        self.__remove_feng = removeFeng
        
    @property
    def removeArrow(self):
        return self.__remove_arrow
    
    def setRemoveArrow(self, removeArrow):
        self.__remove_arrow = removeArrow
        
    @property
    def gangCount(self):
        return self.__gang_count
    
    def setGangCount(self, gangCount):
        self.__gang_count = gangCount
        
    def incGangCount(self):
        self.setGangCount(self.gangCount + 1)
        
    def printTiles(self):
        """打印牌桌手牌信息"""
        ftlog.debug('MTableTile.printTiles...')
        ftlog.debug('addTiles:', self.addTiles)
        ftlog.debug('dropTiles:', self.dropTiles)
        ftlog.debug('menTiles:', self.menTiles)
        ftlog.debug('specialTiles:', self.specialTiles)
        ftlog.debug('leftTiles:', self.tiles)
    
    @property
    def qiangGangRule(self):
        return self.__qiang_gang_rule
    
    def setQiangGangRule(self, rule):
        self.__qiang_gang_rule = rule
    
    @property
    def magicGangMaxCount(self):
        return self.__magics_gang_max_count
    
    def setMagicGangMaxCount(self, magicGangCount):
        self.__magics_gang_max_count = magicGangCount
    
    @property
    def players(self):
        return self.__players
    
    def setPlayers(self, players):
        self.__players = players
        
    @property
    def specialTiles(self):
        return self.__special_tiles
        
    @property
    def runMode(self):
        return self.__run_mode
    
    def addSpecialTile(self, tile):
        self.__special_tiles.append(tile)
    
    @property
    def tileTestMgr(self):
        return self.__tile_test_mgr
                
    @property
    def tiles(self):
        return self.__tiles
    
    @property
    def playCount(self):
        return self.__player_count
    
    @property
    def playMode(self):
        return self.__play_mode
    
    @property
    def dropTiles(self):
        return self.__drop_tiles
    
    @property
    def addTiles(self):
        return self.__add_tiles
    
    @property
    def menTiles(self):
        return  self.__men_tiles
    
    def copyMenTiles(self):
        return copy.deepcopy(self.menTiles)

    @property
    def horseTiles(self):
        return  self.__horse_tiles

    def addHorseTiles(self, tile):
        self.__horse_tiles.append(tile)

    @property
    def tableConfig(self):
        return self.__table_config

    def setTableConfig(self, config):
        """设置牌桌配置"""
        self.__table_config = config
    
    @property
    def dealer(self):
        return self.__dealer
    
    def setAddTileInfo(self, tile, seatId):
        """设置摸牌信息"""
        self.__add_tiles[seatId].append(tile)

    def flowerScores(self, seatId):
        """玩家花分"""
        return self.__flower_scores[seatId]

    def addFlowerScores(self, score, seatId):
        """累加花分"""
        ftlog.debug("addFlowerScores = ", score , '  ', seatId)
        self.__flower_scores[seatId] = self.__flower_scores[seatId] + score

    def flowerTiles(self, seatId):
        """玩家花牌信息"""
        return self.__flower_tiles[seatId]
    
    def reChooseDealer(self):
        """选择发牌器时，还没有传配置
           这里是根据配置重新选择发牌器
           在子类中实现"""
        pass

    def setFlowerTileInfo(self, tile, seatId):
        """设置花牌信息"""
        self.__flower_tiles[seatId].append(tile)

    def setMenTileInfo(self, tile, seatId):
        """设置门前的牌"""
        ftlog.debug('MTableTile.setMenTileInfo seatId:', seatId
                    , ' tile:', tile
                    , ' after add dropTiles:', self.menTiles[seatId])
        self.__men_tiles[seatId].append(tile)
        
    def shuffle(self, goodPointCount, handTileCount):
        """
        洗牌器 
        子类里可添加特殊逻辑，比如确定宝牌
        """
        if self.tileTestMgr.initTiles():
            # 检查手牌
            handTiles = self.tileTestMgr.handTiles
            poolTiles = self.tileTestMgr.tiles
            ftlog.debug("self.tiles len1 = ", len(self.__tiles), "poolTiles = ", poolTiles, "handTiles = ", handTiles)
            if self.__dealer.initTiles(handTiles, poolTiles):
                ftlog.debug("self.tiles len2 = ", len(self.__tiles), "poolTiles = ", poolTiles, "handTiles = ", handTiles)
                self.__tiles = copy.deepcopy(self.__dealer.tiles)
            ftlog.debug("self.tiles len3 = ", len(self.__tiles), "poolTiles = ", poolTiles, "handTiles = ", handTiles)
        else:
            ftlog.debug("self.tiles len4 = ", len(self.__tiles))
            self.__tiles = self.__dealer.shuffle(goodPointCount, handTileCount)
            ftlog.debug("self.tiles len5 = ", len(self.__tiles))
        ftlog.info('MTableTile.shuffle tiles:', self.__tiles)
        
        if self.removeFeng:
            self.__tiles = filter(lambda x:not MTile.isFeng(x), self.__tiles)
        if self.removeArrow:
            self.__tiles = filter(lambda x:not MTile.isArrow(x), self.__tiles)
        
        if self.isRemoveWanTile:
            self.__tiles = filter(lambda x:MTile.getColor(x) == MTile.TILE_WAN, self.__tiles)
         
        return self.__tiles
    
    def getTiles(self):
        """获取本局未发出的手牌，亦即剩余手牌
        """
        return self.__tiles
    
    def getTilesLeftCount(self):
        """获取剩余手牌数量"""
        return len(self.__tiles)
 
    def getCheckFlowCount(self):
        """获取用于流局判定的剩余牌数,用于某些提前判定流局的,例如云南曲靖,如需要由子类覆盖"""
        return len(self.__tiles)

    def getFlowCount(self):
        """获取用于流局判定的剩余牌数,用于某些提前判定流局的"""
        return 0

    def getTileLeftCount(self, tile):
        """获取某个tile剩余数量"""
        tileArr = MTile.changeTilesToValueArr(self.__tiles)
        return tileArr[tile]
    
    def getVisibleTilesCount(self, tile, withHandTiles=False, seatId=-1):
        """从玩家的吃牌/碰牌/打出牌中获取某个花色的数量"""
        visibleTiles = []
        for men in self.__men_tiles:
            visibleTiles.extend(men)
        
        for player in self.players:
            cs = player.copyChiArray()
            for chi in cs:
                visibleTiles.extend(chi)
                
            ps = player.copyPengArray()
            for peng in ps:
                visibleTiles.extend(peng)
                
            gs = player.copyGangArray()
            for gang in gs:
                # 别人的暗杠不计算在内
                if player.curSeatId != seatId:
                    if gang['style'] and len(gang['pattern']):
                        visibleTiles.extend(gang['pattern'])
                else:
                    visibleTiles.extend(gang['pattern'])
                    
            maos = player.copyMaoTile()
            for mao in maos:
                if len(mao['pattern']):
                    visibleTiles.extend(mao['pattern'])
            
            # 添加胡的牌
            huTiles = player.copyHuArray()
            visibleTiles.extend(huTiles)

            if withHandTiles:
                if player.curSeatId == seatId:
                    hand = player.copyHandTiles()
                    visibleTiles.extend(hand)
                    ftlog.debug('TableTile.getVisibleTilesCountWithHandTiles tile:', tile
                                , ' count In Hand Tiles:', hand
                                , ' withHandTiles:', withHandTiles)
                else:
                    ftlog.debug('TableTile.getVisibleTilesCountWithHandTiles tile:', tile
                                , ' seatId:', seatId
                                , ' not hit player seatId:', player.curSeatId)
         
        count = 0       
        for t in visibleTiles:
            if t == tile:
                count += 1
        
        # 去掉一炮多响的影响
        if tile in self.multiTileNum:
            count -= self.multiTileNum[tile]
            
        ftlog.debug('TableTile.getVisibleTilesCount tile:', tile
                , ' count In Visible Tiles:', count
                , ' visibleTiles:', visibleTiles
                , 'multiTileNum:', self.multiTileNum) 
        # count的值不应该大于4    
        count = 4 if count > 4 else count
        
        return count 
        
    def popTile(self, tileLen):
        """从前面弹出多少牌
        子类里可添加特殊逻辑，比如摸牌好牌点
        参数：
        1）len - 弹出牌的长度
        """
        if len(self.__tiles) < tileLen:
            return []
        
        pops = []
        for _ in range(tileLen):
            pops.append(self.__tiles.pop(0))
            
#         ftlog.debug( 'MTableTile.popCard:', pops )
        return pops
    
    def setDropTileInfo(self, tile, seatId):
        """出牌
        记录出牌信息
        子类里可添加特殊逻辑，比如哈尔滨，底牌里有三张宝牌后，需更换宝牌
        """
        self.__drop_tiles[seatId].append(tile)
    
    def canUseMagicTile(self, state):
        """在状态state下是否使用癞子牌"""
        return False
    
    def getMagicTiles(self, isTing=False):
        """获取宝牌，采用数组，有的游戏有多个宝牌"""
        return []

    def getMagicFactors(self, isTing=False):
        """获取赖子皮"""
        return []
    
    def getAbandonedMagics(self):
        """获取废弃的宝牌"""
        return []
    
    def exculeMagicTiles(self, tileArr, magics):
        """挑出癞子牌"""
        magicTiles = []
        if len(magics) != 0:
            for mTile in magics:
                for _ in range(0, tileArr[mTile]):
                    magicTiles.append(mTile)
                tileArr[mTile] = 0
        return tileArr, magicTiles

    def getLastSpecialTiles(self, default=None):
        """获取最后抓取的特殊牌"""
        return []

    def getPigus(self):
        """获取用于补杠的尾牌"""
        return None
    
    def updatePigu(self, tile):
        """更新屁股"""
        return None
    
    def updateMagicTile(self):
        """更新宝牌"""
        return None
    
    def addPassHuBySeatId(self, seatId, tile):
        pass
        
    def clearPassHuBySeatId(self, seatId):
        pass

    def isPassHuTileBySeatId(self, seatId, tile):
        return False

    def isHaveTing(self):
        '''
        是否有听牌的动作
        '''
        return True
    
    def getTingLiangMode(self):
        """默认在听牌时，不会亮牌"""
        # mode 0表示，不亮牌
        return self.MODE_LIANG_NONE

    def canGangAfterPeng(self):
        """一般麻将默认不允许碰后马上杠牌"""
        return False

    def canShowBaoAfterTing(self):
        """玩家没有听牌时，不显示宝牌"""
        return True

    def getTingGangMode(self):
        """一般麻将听牌后只能杠不影响听口的牌"""
        return MTableTile.AFTER_TING_HU_WITHOUT_ANGANG

    def canGangLastTile(self):
        """默认摸到最后一张牌，可以杠牌"""
        return True

    def canGangThisTile(self, tile):
        """能否杠这张牌"""
        return True

    def selectGangAfterTing(self):
        """听牌之后杠是否需要选择"""
        return False

    def canDuoHu(self):
        """是否允许一炮多响"""
        return False

    def isFlower(self, tile):
        """判断tile是否花牌"""

    @property
    def isRemoveWanTile(self):
        return False

    def getAllTilesForTing(self):
        return MTile.TilesForTing