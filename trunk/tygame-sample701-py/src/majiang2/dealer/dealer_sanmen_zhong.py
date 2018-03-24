# -*- coding=utf-8
'''
Created on 2016年9月24日

@author: zhaol
'''
from majiang2.dealer.dealer import Dealer
import random
from majiang2.tile.tile import MTile
from freetime5.util import ftlog

class SanMenWithZhonggDealer(Dealer):
    def __init__(self):
        """初始化
            子类在自己的初始化方法里，初始化麻将牌池范围，准备发牌
            多余红中麻将/哈尔滨麻将
            包括万/筒/条三门+红中
        """
        super(SanMenWithZhonggDealer, self).__init__()
        # 本玩法包含的花色
        self.__card_colors = [MTile.TILE_WAN, MTile.TILE_TONG, MTile.TILE_TIAO, MTile.TILE_FENG]
        # 风牌的描述
        self.__feng_details = MTile.FENG_ZHONG
        # 花色数量
        self.__card_count = len(self.__card_colors)
        # 初始化本玩法包含的牌
        self.setCardTiles(MTile.getTiles(self.__card_colors, self.__feng_details))
        
    def reset(self):
        """重置"""
        super(SanMenWithZhonggDealer, self).reset()
    
    """洗牌/发牌
        子类必须实现
    """
    def shuffle(self, goodPointCount, cardCountPerHand):
        """参数说明
            goodPointCount : 好牌点的人数
            cardCountPerHand ： 每手牌的麻将牌张数
        """
        for color in self.__card_colors:
            print 'cardTiles:', self.cardTiles[color], ' color:', color
            self.addTiles(self.cardTiles[color])

        # 对剩余的牌洗牌
        random.shuffle(self.tiles)
        ftlog.debug('SanMenWithZhonggDealer.shuffle tiles:', self.tiles)
            
        return self.tiles
    
if __name__ == "__main__":
    dealer = SanMenWithZhonggDealer()
    # 牡丹江刮大风
#     dealer.generateTiles({
#                         "seat1": [27,28,29,4,4,4,5,7,15,15,24,25,26],
#                         "seat2": [],
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [3,0,0,0,4],
#                         "magics": [22]
#                         })
    
    # 牡丹江夹胡刮大风
#     dealer.generateTiles({
#                         "seat1": [24,24,24,11,12,13,22,22,22,27,27,27,21],
#                         "seat2": [],
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [4,0,0,0,1],
#                         "magics": [22]
#                         })
    # 牡丹江测试刮大风/夹胡
#     dealer.generateTiles({
#                         "seat1": [24,24,24,12,12,12,1,1,1,3,27,27,27],
#                         "seat2": [],
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [4,0,0,0,1],
#                         "magics": [5]
#                         })
    
    # 哈尔滨测试换宝
#     dealer.generateTiles({
#                         "seat1": [1,1,1,12,12,12,8,8,3,4,4,5,7],
#                         "seat2": [],
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [3,8],
#                         "magics": [6,8]
#                         })
    
    # 牡丹江刮大风宝中宝
#     dealer.generateTiles({
#                           "seat1": [1,1,1,12,12,12,6,6,6,4,4,7,8],
#                           "seat2": [],
#                           "seat3": [],
#                           "seat4": [],
#                           "pool": [8,8,8],
#                           "magics": [6]
#                           })    
    # 牡丹江换宝漏胡
#     dealer.generateTiles({
#                           "seat1": [1,1,1,12,12,12,3,3,3,4,4,5,7],
#                           "seat2": [],
#                           "seat3": [],
#                           "seat4": [],
#                           "pool": [8,8,8],
#                           "magics": [6,8]
#                           })

    # 牡丹江换宝刮大风漏胡
#     dealer.generateTiles({
#                           "seat1": [1,1,1,12,12,12,3,3,3,4,4,5,7],
#                           "seat2": [],
#                           "seat3": [],
#                           "seat4": [],
#                           "pool": [8,8,8],
#                           "magics": [1,8]
#                           })
    # 牡丹江上听漏宝
#     dealer.generateTiles({
#                           "seat1": [1,1,1,12,12,12,3,3,3,4,4,5,7],
#                           "seat2": [],
#                           "seat3": [],
#                           "seat4": [],
#                           "pool": [8,8,8],
#                           "magics": [6]
#                           })

    # 测试换宝
    # 鸡西换宝
#     dealer.generateTiles({
#                         "seat1": [27,25,26,11,11,11,15,17,15,15,24,25,26],
#                         "seat2": [],
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [6,6,6,7,9,7,7,8,9,8,8],
#                         "magics": [8,7,6]
#                         })
    
    # 哈尔滨 测试漏胡
#     dealer.generateTiles({
#                         "seat1": [1,1,22,22,22,3,3,4,5,6,8,9,17], # 漏7
#                         "seat2": [11,11,11,22,23,13,13,13,14,14,1,18,19], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [],
#                         "magics": [7]
#                         })
    
    # 牡丹江不夹不胡
#     dealer.generateTiles({
#                         "seat1": [17,17,17,7,8,9,25,25,26,27,27,28,28], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [],
#                         "magics": [35]
#                         })
    
#     # 牡丹江单调算夹
#     dealer.generateTiles({
#                         "seat1": [17,17,17,7,8,9,21,26,26,27,27,28,28], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [],
#                         "magics": [35]
#                         })
    
#     # 牡丹江宝中宝，只有不夹不胡
#     dealer.generateTiles({
#                         "seat1": [4,4,4,6,6,6,13,13,16,18,27,28,29], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [16,17],
#                         "magics": [17]
#                         })
    
#     # 牡丹江漏宝，漏宝之后基本牌型不对
#     dealer.generateTiles({
#                         "seat1": [11,12,13,23,23,23,1,2,17,18,19,19,19], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [1],
#                         "magics": [19]
#                         })
    
#     # 牡丹江漏宝 大扣暗杠刮大风
#     dealer.generateTiles({
#                         "seat1": [5,6,7,9,9,13,15,17,17,17,23,24,25], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [1],
#                         "magics": [17]
#                         })
    
#     # 牡丹江先吃，再吃，碰听4条，摸4条刮大风胡
#     dealer.generateTiles({
#                         "seat1": [1,2,5,11,12,15,24,24,25,25,26,26,29], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [6,6,6,3,7,7,13,1,24,2,2,2,24],
#                         "magics": [17]
#                         })
    
#     # 牡丹江，先吃再碰9条，摸9条后上听，摸6条，不影响听口的情况下开杠9条。正确结果，不应该开杠9条。
#     dealer.generateTiles({
#                         "seat1": [3,4,4,12,14,15,16,25,27,28,29,29,35], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [0,0,0,17,29,0,0,0,29,0,0,0,26],
#                         "magics": [6,6]
#                         })

#     # 鸡西天胡
#     dealer.generateTiles({
#                         "seat1": [4,4,4,13,14,15,16,16,27,28,29,35,35], # 漏7
#                         "seat2": [], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [35],
#                         "magics": [6]
#                         })

#     # 牡丹江 海底捞 胡牌
#     dealer.generateTiles({
#                         "seat1": [5, 6, 7, 9, 9, 13, 19, 17, 17, 17, 23, 24, 25], # 漏7
#                         "seat2": [18,18,26,9,26,27,28,29,11,11,11,19,19], #抢听11，胡17
#                         "seat3": [],
#                         "seat4": [],
#                         "pool": [18],
#                         "magics": [18]
#                         })
    
    # 哈尔滨漏胡+接连上听+卡死
    dealer.generateTiles({
                        "seat1": [17, 17, 17, 11, 13, 5, 6, 7, 12, 14, 15, 15, 8], # 漏7
                        "seat2": [25], #抢听11，胡17
                        "seat3": [6, 7, 24, 26, 29, 29, 21, 22, 24, 21, 29],
                        "seat4": [17, 12],
                        "pool": [],
                        "magics": [13]
                        })