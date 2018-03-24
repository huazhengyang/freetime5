# -*- coding=utf-8 -*-
'''
Created on 2015年9月30日
麻将好友桌的牌桌，负责好友桌号的管理和好友桌赛制的调度。
@author: 赵良
'''
from freetime5.util import ftlog
from majiang2.ai.play_mode import MPlayMode
from majiang2.entity import majiang_conf
from majiang2.entity import util
from majiang2.entity.create_table import CreateTableData
from majiang2.table.friend_table_define import MFTDefine
from majiang2.table.majiang_quick_table import MajiangQuickTable
from majiang2.table.table_config_define import MTDefine
from majiang2.table.user_leave_reason import MUserLeaveReason
import random
from tuyoo5.core import tyglobal
from majiang2.poker2.entity.game.tables.table_player import TYPlayer
from majiang2.poker2.entity.game.rooms.room import TYRoom


class MajiangFriendTable(MajiangQuickTable):
    # 解散同意
    DISSOLVE_AGREE = 1
    # 解散拒绝
    DISSOLVE_REFUSE = 0
    
    """
    好友桌的牌桌管理类，继承自MajiangQuickTable
    与MajiangQuickTable相比，有几个地方不同。
    1）角色区分房主非房主
    2）准备阶段，房主退出，房间解散，归还全部房卡
    3）牌局开始后，退出走投票机制
    4）自建桌有局数设置，所有的局数打完，散桌。没打完时，继续准备开始下一局
    """
    def __init__(self, tableId, room):
        super(MajiangFriendTable, self).__init__(tableId, room)
        self.__init_params = None
        self.__ftId = None
        self.__table_owner = 0
        self.__vote_info = [None for _ in range(self.maxSeatN)]
        self.__vote_host = MTDefine.INVALID_SEAT
        self.__vote_time_out = 0
        self.__table_owner_seatId = MTDefine.INVALID_SEAT
        self.__ready_time_out_timer = False
        # 用户操作超时
        self.__cur_seat = 0
        # 当前的无用户操作时间
        self.__cur_no_option_time_out = -1
        # 是否试炼场
        self.__is_practice = False
        
    @property
    def isPractice(self):
        return self.__is_practice
    
    def setPractice(self, isPractice):
        self.__is_practice = isPractice
     
    @property
    def readyTimeOutTimer(self):
        return self.__ready_time_out_timer
        
    @property
    def tableOwner(self):
        return self.__table_owner
        
    @property
    def tableOwnerSeatId(self):
        return self.__table_owner_seatId
    
    @property
    def curSeat(self):
        return self.__cur_seat
    
    @property
    def curNoOptionTimeOut(self):
        """当前的无用户操作时间"""
        return self.__cur_no_option_time_out
        
    @property
    def initParams(self):
        return self.__init_params
    
    @property
    def ftId(self):
        return self.__ftId
    
    @property
    def voteInfo(self):
        return self.__vote_info
    
    def setVoteInfo(self, info):
        self.__vote_info = info
    
    @property
    def voteHost(self):
        return self.__vote_host
    
    def setVoteHost(self, host):
        self.__vote_host = host
    
    @property
    def voteTimeOut(self):
        return self.__vote_time_out
    
    def setVoteTimeOut(self, timeOut):
        self.__vote_time_out = timeOut

    '''
    自定义排序玩家勾选参数顺序
    '''
    def customSort(self, initParams):
        customSortList = ['shareFangka', 'cardCount', 'maiMa', 'maxFan', 'dingPiao']
        customSortDict = {}
        for key in customSortList:
            if initParams.has_key(key):
                customSortDict[key] = initParams.get(key)
        for key in initParams:
            if customSortDict.has_key(key) == False:
                customSortDict[key] = initParams.get(key)
        return customSortDict 

    def sendMsgTableInfo(self, msg, userId, seatId, isReconnect, isHost=False):
        """用户坐下后给用户发送table_info"""
        if msg and msg.getParam('itemParams', None):
            initParams = msg.getParam('itemParams', None)  # 玩家选定参数
            self.__init_params = initParams
            self._params_desc, self._params_play_desc = self.get_select_create_config_items()  # 配置项对应的参数及值
            self._params_option_name = self.get_select_create_config_options()  # 配置项对应的名称
            self._params_option_info = self.get_select_create_config_infos()
            self.__is_practice = msg.getParam('hasRobot', 0)
            ftlog.info('MajiangFriendTable.sendMsgTableInfo userId:', userId
                , ' seatId:', seatId
                , ' message:', msg
                , ' itemParams:', self.__init_params
                , ' isPractice', self.isPractice
                , ' paramsDesc:', self.paramsDesc
                , ' paramsPlayDesc:', self.paramsPlayDesc
                , ' paramsOptionName', self.paramsOptionName
                , ' paramsOptionInfo', self.paramsOptionInfo
            )
            
            ftId = msg.getParam('ftId', None)
            if ftId:
                self.processCreateTableSetting()
                self.__ftId = ftId
                # 保存自建桌对应关系
                CreateTableData.addCreateTableNo(self.tableId, self.roomId, tyglobal.serverId(), self.ftId, self.initParams)
                        
                self.__table_owner = userId
                self.__table_owner_seatId = seatId
                self.logic_table.tableConfig[MFTDefine.FTID] = self.ftId
                self.logic_table.tableConfig[MFTDefine.FTOWNER] = userId
                self.logic_table.tableConfig[MFTDefine.ITEMPARAMS] = self.initParams
                self.logic_table.tableConfig[MFTDefine.CREATE_TABLE_DESCS] = self.paramsDesc
                self.logic_table.tableConfig[MFTDefine.CREATE_TABLE_OPTION_NAMES] = self.paramsOptionName
                self.logic_table.tableConfig[MFTDefine.CREATE_TABLE_PLAY_DESCS] = self.paramsPlayDesc
                self.logic_table.tableConfig[MFTDefine.CREATE_TABLE_PLAY_INFO] = self.paramsOptionInfo
                # 返回房主建房成功消息，准备状态
                self.playerReady(self.getSeatIdByUserId(userId), True)
                self.logic_table.msgProcessor.create_table_succ_response(userId
                        , self.getSeatIdByUserId(userId)
                        , 'ready'
                        , 1)
                # 房主启动准备定时器，超时解散牌桌，利用todoTask
                message = self.logic_table.msgProcessor.getMsgReadyTimeOut()
                ftlog.debug('MajiangFriendTable.sendMsgTableInfo msg:', message)
                readyTimeOut = self.getTableConfig(MFTDefine.READY_TIMEOUT, 3600)
                ftlog.debug('MajiangFriendTable.sendMsgTableInfo begin to check ready timeout, message:', message
                        , ' readyTimeOut:', readyTimeOut
                        , ' tableOwnerSeatId:', self.tableOwnerSeatId)
                self.tableTimer.setupTimer(self.tableOwnerSeatId, readyTimeOut, message)
                self.__ready_time_out_timer = True
        # 发送table_info
        super(MajiangFriendTable, self).sendMsgTableInfo(msg, userId, seatId, isReconnect, userId == self.__table_owner)
        # 如果正在投票解散，给用户补发投票解散的消息
        if self.logic_table.isFriendTablePlaying() and self.voteHost != MTDefine.INVALID_SEAT:
            # 补发投票解散信息
            self.logic_table.msgProcessor.create_table_dissolve_vote(self.players[self.voteHost].userId
                    , self.voteHost
                    , self.maxSeatN
                    , self.get_leave_vote_info()
                    , self.get_leave_vote_info_detail()
                    , self.logic_table.player[self.voteHost].name
                    , self.__vote_time_out)   
    
    def get_select_create_config_items(self):
        """
        获取自建桌创建的选项描述
            显示完整的配置需前端上传所有的配置
            
            返回值1，paramsDesc - 分享时的建桌参数，包含人数和局数
            返回值2，paramsPlayDesc - 在牌桌上显示的建桌参数，不包含人数和局数
            
        """
        paramsDesc = []
        paramsPlayDesc = []
        
        create_table_config = majiang_conf.getCreateTableTotalConfig(self.gameId)
        playmode_config = {}
        if create_table_config:
            playmode_config = create_table_config.get(self.playMode, {})
            
        playerTypeId = self.initParams.get(MFTDefine.PLAYER_TYPE, 1)
        playerTypeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.PLAYER_TYPE, playerTypeId)
        cardCardKey = playerTypeConfig.get(MFTDefine.CARD_COUNT, MFTDefine.CARD_COUNT)
            
        # 通过id直接获取自建桌配置的key数组
        for key, value in self.__init_params.iteritems():
            if (key not in playmode_config) or ((MFTDefine.CARD_COUNT in key) and (key != cardCardKey)):
                continue
            
            items = playmode_config[key]
            for item in items:
                ftlog.debug('get_select_create_config_items item:', item, ' value:', value)
                if item['id'] == value:
                    if (key == cardCardKey) or (key == 'playerType'):
                        paramsDesc.append(item['desc'])
                    else:
                        paramsDesc.append(item['desc'])
                        paramsPlayDesc.append(item['desc'])
                    
        ftlog.debug('get_select_create_config_items paramsDesc:', paramsDesc
                    , ' paramsPlayDesc:', paramsPlayDesc)
        return paramsDesc, paramsPlayDesc
    
    def get_select_create_config_infos(self):
        '''
        传递给前端list 用户桌布显示
        return [[血战麻将.换三张],[8倍封顶],[]]
        '''
        if self.playMode != MPlayMode.XUEZHANDAODI and self.playMode != MPlayMode.XUELIUCHENGHE and self.playMode != MPlayMode.JIPINGHU:
            return None
        ret = ['' for _ in range(3)]
        playmode_config = {}
        create_table_config = majiang_conf.getCreateTableTotalConfig(self.gameId)
        if create_table_config:
            playmode_config = create_table_config.get(self.playMode, {})
            ftlog.debug('get_select_create_config_infos playmode_config descs:', playmode_config , 'playMode:', self.playMode)
        
        if 'playModeDesc' in playmode_config:
            ret[0] += playmode_config['playModeDesc']
        
        threeTilesId = self.initParams.get(MTDefine.THREE_TILE_CHANGE, 0)
        if threeTilesId and 'threeTiles' in playmode_config:
            for info in playmode_config['threeTiles']:
                if threeTilesId == info['id']:
                    ret[0] += "." + info['desc']
        
        maxFanId = self.initParams.get('maxFan', 0)
        if maxFanId and 'maxFan' in playmode_config:
            ftlog.debug('get_select_create_config_infos maxFanId:', maxFanId, 'desc:', playmode_config['maxFan'])
            for info in playmode_config['maxFan']:
                if maxFanId == info['id']:
                    ret[1] += info['desc']
        
        ftlog.debug('get_select_create_config_infos playmode_config ret:', ret)
        return ret

        
    def get_select_create_config_options(self):
        """获取自建桌创建的选项
        """
        ret = []
        create_table_config = majiang_conf.getCreateTableTotalConfig(self.gameId)
        playmode_config = {}
        if create_table_config:
            playmode_config = create_table_config.get(self.playMode, {})
            ftlog.debug('get_select_create_config_options playmode_config descs:', playmode_config , 'playMode:', self.playMode)
            
        playerTypeId = self.initParams.get(MFTDefine.PLAYER_TYPE, 1)
        playerTypeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.PLAYER_TYPE, playerTypeId)
        cardCardKey = playerTypeConfig.get(MFTDefine.CARD_COUNT, MFTDefine.CARD_COUNT)
            
        # 通过id直接获取自建桌配置的key数组 前端传递过来的paramType的key
        ftlog.debug('get_select_create_config_options __init_params descs:', self.__init_params
                    , ' playMode:', self.playMode)

        for key, _ in self.__init_params.iteritems():
            if (key not in playmode_config) or ((MFTDefine.CARD_COUNT in key) and (key != cardCardKey)):
                continue
            
            if self.playMode == MPlayMode.XUEZHANDAODI \
                or self.playMode == MPlayMode.XUELIUCHENGHE:
                prarmType = playmode_config['paramType']
                wanFa = playmode_config['wanFa']
                if key in prarmType:
                    name = prarmType[key]['name']
                    ret.append(name)
                else:
                    for wa in wanFa:
                        if key == wa['id']:
                            ret.append(wa['desc'])
            else:
                ftlog.debug('get_select_create_config_options names descs:', playmode_config, ' key:', key)
                prarmType = playmode_config['paramType']
                if key in prarmType:
                    ret.append(prarmType[key])
                    
        ftlog.debug('get_select_create_config_names descs:', ret)
        return ret
    
    def getTableScore(self):
        '''
        取得当前桌子的快速开始的评分
        越是最适合进入的桌子, 评分越高, 座位已满评分为0
        '''
        if self.maxSeatN <= 0 :
            ftlog.info('MajiangFriendTable.getTableScore return 1')
            return 1
        
        # 自建桌逻辑特殊，有人坐下后，后续就不安排人坐下了
        if self.realPlayerNum > 0:
            ftlog.info('MajiangFriendTable.getTableScore friendTable has User, return 0')
            return 0
        
        return (self.realPlayerNum + 1) * 100 / self.maxSeatN
  
    def processCreateTableSetting(self):
        """解析处理自建桌参数"""
        # 配置0 人数
        playerTypeId = self.initParams.get(MFTDefine.PLAYER_TYPE, 1)
        playerTypeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.PLAYER_TYPE, playerTypeId)
        cardCardKey = playerTypeConfig.get(MFTDefine.CARD_COUNT, MFTDefine.CARD_COUNT)
        ftlog.debug('MajiangFriendTable.processCreateTableSetting playerTypeConfig:', playerTypeConfig
                    , ' cardCountKey:', cardCardKey)
        
        # 配置1 轮数
        cardCountId = self.initParams.get(cardCardKey, -1)
        cardCountConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, cardCardKey, cardCountId)
        if self.isPractice:
            cardCountConfig = cardCountConfig.get('hasRobot', cardCountConfig)
        ftlog.info('MajiangFriendTable.processCreateTableSetting cardCountConfig:', cardCountConfig)

        if cardCountConfig:
            cType = cardCountConfig.get('type', MFTDefine.CARD_COUNT_ROUND)
            cValue = cardCountConfig.get('value', 1)
            cCount = cardCountConfig.get('fangka_count', 1)
            self.logic_table.initScheduleMgr(cType, cValue, cCount)
                
        # 配置1-2 daKou
        daKouId = self.initParams.get('daKou', 0)
        daKouConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'daKou', daKouId)
        if daKouConfig:
            self.logic_table.tableConfig[MTDefine.DA_KOU] = daKouConfig.get(MTDefine.DA_KOU, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting daKou:', self.logic_table.tableConfig[MTDefine.DA_KOU])
              
        # 配置 底分
        winBaseId = self.initParams.get('winBase', 0)
        winBaseConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'winBase', winBaseId)
        if winBaseConfig:
            difen = winBaseConfig.get(MTDefine.WIN_BASE, 1)
            self.logic_table.tableConfig[MTDefine.WIN_BASE] = difen
            ftlog.debug('MajiangFriendTable.processCreateTableSetting winBase:', self.logic_table.tableConfig[MTDefine.WIN_BASE])
            # 牡丹江杠分
            if self.playMode == MPlayMode.MUDANJIANG:
                if difen == 2:
                    self.logic_table.tableConfig[MTDefine.GANG_BASE] = 5
                elif difen == 5:
                    self.logic_table.tableConfig[MTDefine.GANG_BASE] = 10

        # 配置 杠分
        gangBaseId = self.initParams.get('gangBase', 0)
        gangBaseConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'gangBase', gangBaseId)
        if gangBaseConfig:
            difen = gangBaseConfig.get(MTDefine.GANG_BASE, 1)
            self.logic_table.tableConfig[MTDefine.GANG_BASE] = difen
            ftlog.debug('MajiangFriendTable.processCreateTableSetting gangBase:', self.logic_table.tableConfig[MTDefine.GANG_BASE])
            
        # 配置
        maxScoreId = self.initParams.get('maxLossScore', 0)
        maxScoreConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'maxLossScore', maxScoreId)
        if maxScoreConfig:
            temps = maxScoreConfig.get(MTDefine.MAX_LOSS_SCORE, 256)
            self.logic_table.tableConfig[MTDefine.MAX_LOSS_SCORE] = temps
            ftlog.debug('MajiangFriendTable.processCreateTableSetting maxScore:', self.logic_table.tableConfig[MTDefine.MAX_LOSS_SCORE])
            
        # 配置2 纯夹
        chunJiaId = self.initParams.get('chunJia', 0)
        chunJiaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'chunJia', chunJiaId)
        if chunJiaConfig:
            self.logic_table.tableConfig[MTDefine.MIN_MULTI] = chunJiaConfig.get(MTDefine.MIN_MULTI, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting chunJia:', self.logic_table.tableConfig[MTDefine.MIN_MULTI])
        
        # 配置3 红中宝
        hzbId = self.initParams.get('hongZhongBao', 0)
        hzbConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'hongZhongBao', hzbId)
        if hzbConfig:
            self.logic_table.tableConfig[MTDefine.HONG_ZHONG_BAO] = hzbConfig.get(MTDefine.HONG_ZHONG_BAO, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting hongZhongBao:', self.logic_table.tableConfig[MTDefine.HONG_ZHONG_BAO])
            
        # 配置4 三七边
        sqbId = self.initParams.get('sanQiBian', 0)
        sqbConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'sanQiBian', sqbId)
        if sqbConfig:
            self.logic_table.tableConfig[MTDefine.BIAN_MULTI] = sqbConfig.get(MTDefine.BIAN_MULTI, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting sanQiBian:', self.logic_table.tableConfig[MTDefine.BIAN_MULTI])
        
        # 配置5 刮大风
        fengId = self.initParams.get('guaDaFeng', 0)
        fengConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'guaDaFeng', fengId)
        if fengConfig:
            self.logic_table.tableConfig[MTDefine.GUA_DA_FENG] = fengConfig.get(MTDefine.GUA_DA_FENG, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting guaDaFeng:', self.logic_table.tableConfig[MTDefine.GUA_DA_FENG])

        # 配置6 频道
        pinDaoId = self.initParams.get('pinDao', 0)
        pinDaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'pinDao', pinDaoId)
        if pinDaoConfig:
            self.logic_table.tableConfig[MTDefine.PIN_DAO] = pinDaoConfig.get(MTDefine.PIN_DAO, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting pinDao:', self.logic_table.tableConfig[MTDefine.PIN_DAO])

        # 配置7 跑恰摸八
        paoqiamobaId = self.initParams.get('paoqiamoba', 0)
        paoqiamobaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'paoqiamoba', paoqiamobaId)
        if paoqiamobaConfig:
            self.logic_table.tableConfig[MTDefine.PAOQIAMOBA] = paoqiamobaConfig.get(MTDefine.PAOQIAMOBA, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting paoqiamoba:', self.logic_table.tableConfig[MTDefine.PAOQIAMOBA])

        # 配置8 定漂
        dingPiaoId = self.initParams.get('dingPiao', 0)
        dingPiaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'dingPiao', dingPiaoId)
        if dingPiaoConfig:
            self.logic_table.tableConfig[MTDefine.PIAO_SETTING] = dingPiaoConfig.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting dingPiao:', self.logic_table.tableConfig[MTDefine.PIAO_SETTING])

        # 配置9 买马
        maiMaId = self.initParams.get('maiMa', 0)
        maiMaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'maiMa', maiMaId)
        if maiMaConfig:
            self.logic_table.tableConfig[MTDefine.MAI_MA] = maiMaConfig.get(MTDefine.MAI_MA, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting maiMa:', self.logic_table.tableConfig[MTDefine.MAI_MA])

        # 配置10 数坎
        shuKanId = self.initParams.get('shuKan', 0)
        shuKanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'shuKan', shuKanId)
        if shuKanConfig:
            self.logic_table.tableConfig[MTDefine.SHU_KAN] = shuKanConfig.get(MTDefine.SHU_KAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting shuKan:', self.logic_table.tableConfig[MTDefine.SHU_KAN])

        # 配置11 听牌时亮牌规则
        liangPaiId = self.initParams.get('liangPai', 0)
        liangPaiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'liangPai', liangPaiId)
        if liangPaiConfig:
            self.logic_table.tableConfig[MTDefine.LIANG_PAI] = liangPaiConfig.get(MTDefine.LIANG_PAI, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting liangPai:', self.logic_table.tableConfig[MTDefine.LIANG_PAI])

        # 配置12 最大番数
        maxFanId = self.initParams.get('maxFan', 0)
        maxFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'maxFan', maxFanId)
        if maxFanConfig:
            self.logic_table.tableConfig[MTDefine.MAX_FAN] = maxFanConfig.get(MTDefine.MAX_FAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting maxFan:', self.logic_table.tableConfig[MTDefine.MAX_FAN])

        # 配置13 卡五星番数
        kawuxingFanId = self.initParams.get('kawuxingFan', 0)
        kawuxingFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'kawuxingFan', kawuxingFanId)
        if kawuxingFanConfig:
            self.logic_table.tableConfig[MTDefine.KAWUXING_FAN] = kawuxingFanConfig.get(MTDefine.KAWUXING_FAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting kawuxingFan:', self.logic_table.tableConfig[MTDefine.KAWUXING_FAN])

        # 配置14 碰碰胡番数
        pengpenghuFanId = self.initParams.get('pengpenghuFan', 0)
        pengpenghuFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'pengpenghuFan', pengpenghuFanId)
        if pengpenghuFanConfig:
            self.logic_table.tableConfig[MTDefine.PENGPENGHU_FAN] = pengpenghuFanConfig.get(MTDefine.PENGPENGHU_FAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting pengpenghuFan:', self.logic_table.tableConfig[MTDefine.PENGPENGHU_FAN])

        # 配置15 杠上花番数
        gangshanghuaFanId = self.initParams.get('gangshanghuaFan', 0)
        gangshanghuaFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'gangshanghuaFan', gangshanghuaFanId)
        if gangshanghuaFanConfig:
            self.logic_table.tableConfig[MTDefine.GANGSHANGHUA_FAN] = gangshanghuaFanConfig.get(MTDefine.GANGSHANGHUA_FAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting gangshanghuaFan:', self.logic_table.tableConfig[MTDefine.GANGSHANGHUA_FAN])
            
        # 配置16 闭门算番(鸡西)
        biMenFanId = self.initParams.get('biMenFan', 0)
        biMenFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'biMenFan', biMenFanId)
        if biMenFanConfig:
            self.logic_table.tableConfig[MTDefine.BI_MEN_FAN] = biMenFanConfig.get(MTDefine.BI_MEN_FAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting biMenFan:', self.logic_table.tableConfig[MTDefine.BI_MEN_FAN])
        
        # 配置 天胡（白城可选玩法）
        tianHuId = self.initParams.get('tianHu', 0)
        tianHuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'tianHu', tianHuId)
        if tianHuConfig:
            self.logic_table.tableConfig[MTDefine.TIAN_HU] = tianHuConfig.get(MTDefine.TIAN_HU, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting tianHu:', self.logic_table.tableConfig[MTDefine.TIAN_HU])

        # 配置 责任制（白城可选玩法）
        inchargeId = self.initParams.get('incharge', 0)
        inchargeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'incharge', inchargeId)
        if inchargeConfig:
            self.logic_table.tableConfig[MTDefine.BAOZHUANG_BAOGANG] = inchargeConfig.get(MTDefine.BAOZHUANG_BAOGANG, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting BAOZHUANG_BAOGANG:', self.logic_table.tableConfig[MTDefine.BAOZHUANG_BAOGANG])

        # 配置 liangtoujia（白城可选玩法）
        liangtoujiaId = self.initParams.get('liangtoujia', 0)
        liangtoujiaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'liangtoujia', liangtoujiaId)
        if liangtoujiaConfig:
            self.logic_table.tableConfig[MTDefine.LIANGTOU_JIA] = liangtoujiaConfig.get(MTDefine.LIANGTOU_JIA, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting liangtoujia:', self.logic_table.tableConfig[MTDefine.LIANGTOU_JIA])

        # 配置17 抽奖牌数量(鸡西)
        awordTileCountId = self.initParams.get('awordTileCount', 0)
        awordTileCountConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'awordTileCount', awordTileCountId)
        if awordTileCountConfig:
            self.logic_table.tableConfig[MTDefine.AWARD_TILE_COUNT] = awordTileCountConfig.get(MTDefine.AWARD_TILE_COUNT, 1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting awordTileCount:', self.logic_table.tableConfig[MTDefine.AWARD_TILE_COUNT])
            
        # 配置18 宝牌隐藏(鸡西 默认暗宝)
        magicHideId = self.initParams.get('magicHide', 0)
        magicHideConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'magicHide', magicHideId)
        if magicHideConfig:
            self.logic_table.tableConfig[MTDefine.MAGIC_HIDE] = magicHideConfig.get(MTDefine.MAGIC_HIDE, 1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting magicHide:', self.logic_table.tableConfig[MTDefine.MAGIC_HIDE])
            
        # 配置19 对宝(哈尔滨补充 规则和鸡西通宝一样)
        duiBaoId = self.initParams.get('duiBao', 0)
        duiBaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'duiBao', duiBaoId)
        if duiBaoConfig:
            self.logic_table.tableConfig[MTDefine.DUI_BAO] = duiBaoConfig.get(MTDefine.DUI_BAO, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting duiBao:', self.logic_table.tableConfig[MTDefine.DUI_BAO])
            
        # 配置20 单吊算夹(哈尔滨补充)
        danDiaoJiaId = self.initParams.get('danDiaoJia', 0)
        danDiaoJiaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'danDiaoJia', danDiaoJiaId)
        if danDiaoJiaConfig:
            self.logic_table.tableConfig[MTDefine.DAN_DIAO_JIA] = danDiaoJiaConfig.get(MTDefine.DAN_DIAO_JIA, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting danDiaoJia:', self.logic_table.tableConfig[MTDefine.DAN_DIAO_JIA])
            
        # 配置21 平度麻将的是否允许吃
        allowChiId = self.initParams.get(MFTDefine.ALLOW_CHI, MFTDefine.ALLOW_CHI_NO)
        allowChiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.ALLOW_CHI, allowChiId)
        if allowChiConfig:
            self.logic_table.tableConfig[MTDefine.CHIPENG_SETTING] = allowChiConfig.get(MTDefine.CHIPENG_SETTING, MTDefine.NOT_ALLOW_CHI)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting chiPengSetting1:', self.logic_table.tableConfig[MTDefine.CHIPENG_SETTING])

        # 配置 盘锦麻将的是否允许gang
        allowgangId = self.initParams.get('allowGang', 0)
        allowgangConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'allowGang', allowgangId)
        if allowgangConfig:
            self.logic_table.tableConfig[MTDefine.GANG_SETTING] = allowgangConfig.get(MTDefine.GANG_SETTING, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting GANG_SETTING:', self.logic_table.tableConfig[MTDefine.GANG_SETTING])

        # 配置 盘锦麻将
        jihuId = self.initParams.get('jiHu', 0)
        jihuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'jiHu', jihuId)
        if jihuConfig:
            self.logic_table.tableConfig[MTDefine.JI_HU] = jihuConfig.get(MTDefine.JI_HU, 0)

        # 配置 盘锦麻将
        qiongHuId = self.initParams.get('qiongHu', 0)
        qiongHuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'qiongHu', qiongHuId)
        if qiongHuConfig:
            self.logic_table.tableConfig[MTDefine.QIONG_HU] = qiongHuConfig.get(MTDefine.QIONG_HU, 0)

        # 配置 盘锦麻将
        jueHuId = self.initParams.get('jueHu', 0)
        jueHuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'jueHu', jueHuId)
        if jueHuConfig:
            self.logic_table.tableConfig[MTDefine.JUE_HU] = jueHuConfig.get(MTDefine.JUE_HU, 0)

        # 配置 盘锦麻将
        huiPaiId = self.initParams.get('huiPai', 0)
        huiPaiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'huiPai', huiPaiId)
        if huiPaiConfig:
            self.logic_table.tableConfig[MTDefine.HUI_PAI] = huiPaiConfig.get(MTDefine.HUI_PAI, 0)

        # 配置22，卡五星的吃碰设置
        # 这样做不好，会直接把协议暴漏给外面，需要按照上面的方式修改
        chiPengSetting = self.initParams.get(MTDefine.CHIPENG_SETTING, 0)
        if chiPengSetting != 0:
            self.logic_table.tableConfig[MTDefine.CHIPENG_SETTING] = chiPengSetting
            ftlog.debug('MajiangFriendTable.processCreateTableSetting chiPengSetting2:', chiPengSetting)
            
        # 配置23 输赢倍数
        # 这样做不好，会直接把协议暴漏给外面，需要按照上面的方式修改
        multiNum = self.initParams.get(MTDefine.MULTIPLE, MTDefine.MULTIPLE_MIN)
        if multiNum >= MTDefine.MULTIPLE_MIN and multiNum <= MTDefine.MULTIPLE_MAX:
            self.logic_table.tableConfig[MTDefine.MULTIPLE] = multiNum
            
        # 配置24 必漂分值
        mustPiao = self.initParams.get(MFTDefine.MUST_PIAO, 0)
        mustPiaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.MUST_PIAO, mustPiao)
        if mustPiaoConfig:
            self.logic_table.tableConfig[MTDefine.BIPIAO_POINT] = mustPiaoConfig.get('value', 0)
            
        # 配置25 锚／蛋时间设置
        maodantime = self.initParams.get(MTDefine.MAO_DAN_FANG_TIME, 0)
        maodantimeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.MAO_DAN_FANG_TIME, maodantime)
        if maodantimeConfig:
            self.logic_table.tableConfig[MTDefine.MAO_DAN_FANG_TIME] = maodantimeConfig.get(MTDefine.MAO_DAN_FANG_TIME, 0)

        # 配置26 锚／蛋设置
        maodan = self.initParams.get(MTDefine.MAO_DAN_SETTING, 0)
        maodanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.MAO_DAN_SETTING, maodan)
        if maodanConfig:
            self.logic_table.tableConfig[MTDefine.MAO_DAN_SETTING] = maodanConfig.get(MTDefine.MAO_DAN_SETTING, 0)
            
        # 配置27 必须自摸
        zimo = self.initParams.get(MFTDefine.MUST_ZIMO, 0)
        zimoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.MUST_ZIMO, zimo)
        if zimoConfig:
            self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO] = zimoConfig.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting zimo:', zimo
                        , ' zimoConfig:', zimoConfig
                        , ' zimoConfig in table:', self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO])
            
        # 配置28，去掉风牌箭牌
        noFengTiles = self.initParams.get(MFTDefine.NO_FENG_TILES, 0)
        noFengConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.NO_FENG_TILES, noFengTiles)
        if noFengConfig:
            self.logic_table.tableConfig[MTDefine.REMOVE_FENG_ARROW_TILES] = noFengConfig.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting noFengTiles:', noFengTiles
                        , ' noFengConfig:', noFengConfig
                        , ' noFengConfigInTable:', self.logic_table.tableConfig[MTDefine.REMOVE_FENG_ARROW_TILES])
            
        # 配置29 庄翻倍
        bankerDouble = self.initParams.get(MFTDefine.BANKER_DOUBLE, 0)
        bankerDoubleConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.BANKER_DOUBLE, bankerDouble)
        if bankerDoubleConfig:
            self.logic_table.tableConfig[MTDefine.BANKER_DOUBLE] = bankerDoubleConfig.get('value', 1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting bankerDouble:', bankerDouble
                        , ' bankerDoubleConfig:', bankerDoubleConfig
                        , ' bankerDoubleConfigInTable:', self.logic_table.tableConfig[MTDefine.BANKER_DOUBLE])
            
        # 配置30 门清翻倍
        clearDouble = self.initParams.get(MFTDefine.CLEAR_DOUBLE, 0)
        clearDoubleConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.CLEAR_DOUBLE, clearDouble)
        if clearDoubleConfig:
            self.logic_table.tableConfig[MTDefine.MEN_CLEAR_DOUBLE] = clearDoubleConfig.get('value', 1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting clearDouble:', clearDouble
                        , ' clearDoubleConfig:', clearDoubleConfig
                        , ' clearDoubleConfigInTable:', self.logic_table.tableConfig[MTDefine.MEN_CLEAR_DOUBLE])

        # 配置31 二五八掌
        zhang258 = self.initParams.get(MFTDefine.ZHANG_258, 0)
        zhang258Config = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.ZHANG_258, zhang258)
        if zhang258Config:
            self.logic_table.tableConfig[MTDefine.ONLY_JIANG_258] = zhang258Config.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting zhang258:', zhang258
                        , ' zhang258Config:', zhang258Config
                        , ' zhang258ConfigInTable:', self.logic_table.tableConfig[MTDefine.ONLY_JIANG_258])


        # 配置32 是否乱锚 威海
        luanMao = self.initParams.get(MFTDefine.LUAN_MAO, 0)
        luanMaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.LUAN_MAO, luanMao)
        if self.playMode == 'weihai':
            if luanMaoConfig:  # 乱锚
                self.logic_table.tableConfig[MTDefine.MAO_DAN_SETTING] = luanMaoConfig.get(MTDefine.MAO_DAN_SETTING, MTDefine.MAO_DAN_DNXB + MTDefine.MAO_DAN_ZFB)
                ftlog.debug('MajiangFriendTable.processCreateTableSetting luanMao:', luanMao
                            , ' luanMaoConfig:', luanMaoConfig
                            , ' luanMaoConfigInTable:', self.logic_table.tableConfig[MTDefine.MAO_DAN_SETTING])
            else:  # 不乱锚
                self.logic_table.tableConfig[MTDefine.MAO_DAN_SETTING] = luanMaoConfig.get(MTDefine.MAO_DAN_SETTING, MTDefine.MAO_DAN_DNXBZFB)
                ftlog.debug('MajiangFriendTable.processCreateTableSetting luanMao reset:', luanMao
                            , ' luanMaoConfig:', luanMaoConfig
                            , ' luanMaoConfigInTable:', self.logic_table.tableConfig[MTDefine.MAO_DAN_SETTING])

        # 配置33 必杠模式
        bigang = self.initParams.get('bigang', 0)
        bigangConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'bigang', bigang)
        if bigangConfig:
            self.logic_table.tableConfig[MTDefine.BI_GANG] = bigangConfig.get(MTDefine.BI_GANG, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting bigang:', self.logic_table.tableConfig[MTDefine.BI_GANG])

        # 配置33 玩家牌码
        multiple = self.initParams.get(MTDefine.MULTIPLE, MTDefine.MULTIPLE_MIN)
        multipleConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.MULTIPLE, multiple)
        if multipleConfig:
            initScore = multipleConfig.get(MFTDefine.INIT_SCORE, 0)
            if initScore:
                self.logic_table.tableConfig[MFTDefine.INIT_SCORE] = initScore
            ftlog.debug('MajiangFriendTable.processCreateTableSetting multipleConfig:', multipleConfig
                        , ' initScore:', initScore)

        # 配置34 只许自摸
        needZimo = self.initParams.get('needzimo', 0)
        needZimoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'needzimo', needZimo)
        if needZimoConfig:
            self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO] = needZimoConfig.get(MTDefine.WIN_BY_ZIMO, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting needZimo:', self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO])

        # 配置35 喜相逢分数
        xiXiangFeng = self.initParams.get('xixiangfeng', 0)
        xiXiangFengConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'xixiangfeng', xiXiangFeng)
        if xiXiangFengConfig:
            self.logic_table.tableConfig[MTDefine.XIXIANGFENG] = xiXiangFengConfig.get(MTDefine.XIXIANGFENG, 50)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting xiXiangFeng', self.logic_table.tableConfig[MTDefine.XIXIANGFENG])

        # 配置36 是否均摊房卡
        shareFangka = self.initParams.get('shareFangka', 0)
        shareFangkaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, 'shareFangka', shareFangka)
        if shareFangkaConfig:
            self.logic_table.tableConfig[MTDefine.SHARE_FANGKA] = shareFangkaConfig.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting shareFangkaConfig:', self.logic_table.tableConfig[MTDefine.SHARE_FANGKA])
            
        # 配置37 是否允许听
        canTingId = self.initParams.get(MFTDefine.CAN_TING, MTDefine.TING_UNDEFINE)
        canTingConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.CAN_TING, canTingId)
        if canTingConfig:
            self.logic_table.tableConfig[MTDefine.TING_SETTING] = canTingConfig.get('value', MTDefine.TING_NO)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting tingSetting:', self.logic_table.tableConfig[MTDefine.TING_SETTING])
            
        # 配置38，是否允许漂
        canPiaoId = self.initParams.get(MFTDefine.CAN_PIAO, MTDefine.PIAO_UNDEFINE)
        canPiaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.CAN_PIAO, canPiaoId)
        if canPiaoConfig:
            self.logic_table.tableConfig[MTDefine.PIAO_SETTING] = canPiaoConfig.get('value', MTDefine.PIAO_NO)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting piaoSetting:', self.logic_table.tableConfig[MTDefine.PIAO_SETTING])
          
        # 配置39，是否允许加倍  
        canDoubleId = self.initParams.get(MFTDefine.CAN_DOUBLE, MTDefine.DOUBLE_UNDEFINE)
        canDoubleConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.CAN_DOUBLE, canDoubleId)
        if canDoubleConfig:
            self.logic_table.tableConfig[MTDefine.DOUBLE_SETTING] = canDoubleConfig.get('value', MTDefine.DOUBLE_NO)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting doubleSetting:', self.logic_table.tableConfig[MTDefine.DOUBLE_SETTING])

        # 配置40，胡牌方式
        winSetId = self.initParams.get("winsetting", 0)
        winSetConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, "winsetting", winSetId)
        if winSetConfig:
            self.logic_table.tableConfig[MTDefine.WIN_SETTING] = winSetConfig.get('type', MTDefine.WIN_TYPE1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting winSetting:',
                        self.logic_table.tableConfig[MTDefine.WIN_SETTING])

        # 配置41，初始积分
        initScore = self.initParams.get("initScore", 0)
        initScoreConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, "initScore", initScore)
        if initScoreConfig:
            self.logic_table.tableConfig[MFTDefine.INIT_SCORE] = initScoreConfig.get('value', 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting initScoreConfig:',
                        self.logic_table.tableConfig[MFTDefine.INIT_SCORE])

        # 配置42，对亮对翻
        duiLiangDuiFan = self.initParams.get("duiliangduifan", 0)
        duiLiangDuiFanConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, "duiliangduifan", duiLiangDuiFan)
        if duiLiangDuiFanConfig:
            self.logic_table.tableConfig[MTDefine.DUILIANGDUIFAN] = duiLiangDuiFanConfig.get(MTDefine.DUILIANGDUIFAN, 0)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting duiliangduifan:',
                        self.logic_table.tableConfig[MTDefine.DUILIANGDUIFAN])

        # 配置43，带不带配子
        peiZi = self.initParams.get("peizi", 0)
        peiZiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, "peizi", peiZi)
        if peiZiConfig:
            self.logic_table.tableConfig[MTDefine.PEIZI_SETTING] = peiZiConfig.get('type', MTDefine.PEIZI_TYPE2)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting peiZiConfig:',
                        self.logic_table.tableConfig[MTDefine.PEIZI_SETTING])

        # 配置44，带不带七对、十三不靠
        optionalType = self.initParams.get("optionalType", 0)
        optionalTypeConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, "optionalType", optionalType)
        if optionalTypeConfig:
            self.logic_table.tableConfig[MTDefine.OPTIONAL_SETTING] = optionalTypeConfig.get('type', MTDefine.OPTIONAL_TYPE1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting optionalType:', self.logic_table.tableConfig[MTDefine.OPTIONAL_SETTING])
            
        # 配置45 换三张
        huanSanZhangId = self.initParams.get(MTDefine.THREE_TILE_CHANGE, 0)
        huanSanZhangConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.THREE_TILE_CHANGE, huanSanZhangId)
        if huanSanZhangConfig:
            self.logic_table.tableConfig[MTDefine.THREE_TILE_CHANGE] = huanSanZhangConfig.get('value', MTDefine.THREE_TILE_CHANGE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting huansanzhang:', self.logic_table.tableConfig[MTDefine.THREE_TILE_CHANGE])
        
        # 配置46 呼叫转移
        callTransferId = self.initParams.get(MTDefine.CALL_TRANSFER, 0)
        callTransferConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.CALL_TRANSFER, callTransferId)
        if callTransferConfig:
            self.logic_table.tableConfig[MTDefine.CALL_TRANSFER] = callTransferConfig.get('value', MTDefine.CALL_TRANSFER)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting callTransfer:', self.logic_table.tableConfig[MTDefine.CALL_TRANSFER])
        
        # 配置47 全幺九
        quanyaojiuId = self.initParams.get(MFTDefine.QUANYAOJIU_DOUBLE, 0)
        quanyaojiuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.QUANYAOJIU_DOUBLE, quanyaojiuId)
        if quanyaojiuConfig:
            self.logic_table.tableConfig[MFTDefine.QUANYAOJIU_DOUBLE] = quanyaojiuConfig.get('value', MFTDefine.QUANYAOJIU_DOUBLE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting quanyaojiu:', self.logic_table.tableConfig[MFTDefine.QUANYAOJIU_DOUBLE])
        
        # 配置48 断幺九
        duanyaojiuId = self.initParams.get(MFTDefine.DUANYAOJIU_DOUBLE, 0)
        duanyaojiuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.DUANYAOJIU_DOUBLE, duanyaojiuId)
        if duanyaojiuConfig:
            self.logic_table.tableConfig[MFTDefine.DUANYAOJIU_DOUBLE] = duanyaojiuConfig.get('value', MFTDefine.DUANYAOJIU_DOUBLE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting duanyaojiu:', self.logic_table.tableConfig[MFTDefine.DUANYAOJIU_DOUBLE])
          
        # 配置49 将对
        jiangduiId = self.initParams.get(MFTDefine.JIANGDUI_DOUBLE, 0)
        jiangduiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.JIANGDUI_DOUBLE, jiangduiId)
        if jiangduiConfig:
            self.logic_table.tableConfig[MFTDefine.JIANGDUI_DOUBLE] = jiangduiConfig.get('value', MFTDefine.JIANGDUI_DOUBLE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting jiangdui:', self.logic_table.tableConfig[MFTDefine.JIANGDUI_DOUBLE])
        
        # 配置50 天地胡
        tiandihuId = self.initParams.get(MFTDefine.TIANDIHU_DOUBLE, 0)
        tiandihuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.TIANDIHU_DOUBLE, tiandihuId)
        if tiandihuConfig:
            self.logic_table.tableConfig[MFTDefine.TIANDIHU_DOUBLE] = tiandihuConfig.get('value', MFTDefine.TIANDIHU_DOUBLE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting tiandihu:', self.logic_table.tableConfig[MFTDefine.TIANDIHU_DOUBLE])
        
        # 配置51 海底捞月
        haidilaoyueId = self.initParams.get(MFTDefine.HAIDILAOYUE_DOUBLE, 0)
        haidilaoyueConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MFTDefine.HAIDILAOYUE_DOUBLE, haidilaoyueId)
        if haidilaoyueConfig:
            self.logic_table.tableConfig[MFTDefine.HAIDILAOYUE_DOUBLE] = haidilaoyueConfig.get('value', MFTDefine.HAIDILAOYUE_DOUBLE)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting haidilaoyue:', self.logic_table.tableConfig[MFTDefine.HAIDILAOYUE_DOUBLE])
            
        # 配置52 四川玩法
        playModeWanFaId = self.initParams.get(MTDefine.PLAYMODE_WANFA, 0)
        playModeWanFaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.PLAYMODE_WANFA, playModeWanFaId)
        if playModeWanFaConfig:
            self.logic_table.tableConfig[MTDefine.PLAYMODE_WANFA] = playModeWanFaConfig.get('value', MTDefine.PLAYMODE_WANFA)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting playModeWanFa:', self.logic_table.tableConfig[MTDefine.PLAYMODE_WANFA])
         
        # 配置53 四川玩法 点杠胡
        playModeWanFaId = self.initParams.get(MTDefine.PLAYMODE_WANFA_DIANGANGHUA, 0)
        playModeWanFaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.PLAYMODE_WANFA_DIANGANGHUA, playModeWanFaId)
        if playModeWanFaConfig:
            self.logic_table.tableConfig[MTDefine.PLAYMODE_WANFA_DIANGANGHUA] = playModeWanFaConfig.get('value', MTDefine.PLAYMODE_WANFA_DIANGANGHUA)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting playModeWanFaDianGangHua:', self.logic_table.tableConfig[MTDefine.PLAYMODE_WANFA_DIANGANGHUA])   
        
        # 是否可抢杠胡
        qiangganghuId = self.initParams.get(MTDefine.QIANGGANGHU, 0)
        qiangganghuConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.QIANGGANGHU, qiangganghuId)
        if qiangganghuConfig:
            self.logic_table.tableConfig[MTDefine.QIANGGANGHU] = qiangganghuConfig.get('value', MTDefine.QIANGGANGHU_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting qiangganghu:', self.logic_table.tableConfig[MTDefine.QIANGGANGHU])

        huqiduiId = self.initParams.get(MTDefine.HUQIDUI, 0)
        huqiduiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.HUQIDUI, huqiduiId)
        if huqiduiConfig:
            self.logic_table.tableConfig[MTDefine.HUQIDUI] = huqiduiConfig.get('value', MTDefine.HUQIDUI)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting huqidui:', self.logic_table.tableConfig[MTDefine.HUQIDUI])

        qiduijiabeiId = self.initParams.get(MTDefine.QIDUIJIABEI, 0)
        qiduijiabeiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.QIDUIJIABEI, qiduijiabeiId)
        if qiduijiabeiConfig:
            self.logic_table.tableConfig[MTDefine.QIDUIJIABEI] = qiduijiabeiConfig.get('value', MTDefine.QIDUIJIABEI_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting qiduijiabei:', self.logic_table.tableConfig[MTDefine.QIDUIJIABEI])

        haohuaqidui4beiId = self.initParams.get(MTDefine.HAOHUAQIDUI4BEI, 0)
        haohuaqidui4beiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.HAOHUAQIDUI4BEI, haohuaqidui4beiId)
        if haohuaqidui4beiConfig:
            self.logic_table.tableConfig[MTDefine.HAOHUAQIDUI4BEI] = haohuaqidui4beiConfig.get('value', MTDefine.HAOHUAQIDUI4BEI_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting haohuaqidui4bei:', self.logic_table.tableConfig[MTDefine.HAOHUAQIDUI4BEI])

        genzhuangjiabeiId = self.initParams.get(MTDefine.GENZHUANGJIABEI, 0)
        genzhuangjiabeiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.GENZHUANGJIABEI, genzhuangjiabeiId)
        if genzhuangjiabeiConfig:
            self.logic_table.tableConfig[MTDefine.GENZHUANGJIABEI] = genzhuangjiabeiConfig.get('value', MTDefine.GENZHUANGJIABEI_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting genzhuangjiabei:', self.logic_table.tableConfig[MTDefine.GENZHUANGJIABEI])

        gangkaijiabeiId = self.initParams.get(MTDefine.GANGKAIJIABEI, 0)
        gangkaijiabeiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.GANGKAIJIABEI, gangkaijiabeiId)
        if gangkaijiabeiConfig:
            self.logic_table.tableConfig[MTDefine.GANGKAIJIABEI] = gangkaijiabeiConfig.get('value', MTDefine.GANGKAIJIABEI_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting gangkaijiabei:', self.logic_table.tableConfig[MTDefine.GANGKAIJIABEI])

        qiangganghujiabeiId = self.initParams.get(MTDefine.QIANGGANGHUJIABEI, 0)
        qiangganghujiabeiConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.QIANGGANGHUJIABEI, qiangganghujiabeiId)
        if qiangganghujiabeiConfig:
            self.logic_table.tableConfig[MTDefine.QIANGGANGHUJIABEI] = qiangganghujiabeiConfig.get('value', MTDefine.QIANGGANGHUJIABEI_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting qiangganghujiabei:', self.logic_table.tableConfig[MTDefine.QIANGGANGHUJIABEI])

        laizi = self.initParams.get(MTDefine.LAIZI, 0)
        laiziConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.LAIZI, laizi)
        if laiziConfig:
            self.logic_table.tableConfig[MTDefine.LAIZI] = laiziConfig.get('value', MTDefine.NO_LAIZI)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting laizi:', self.logic_table.tableConfig[MTDefine.LAIZI])  

        fanggangkaichengbaoId = self.initParams.get(MTDefine.FANGGANGKAICHENGBAO, 0)
        fanggangkaichengbaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.FANGGANGKAICHENGBAO, fanggangkaichengbaoId)
        if fanggangkaichengbaoConfig:
            self.logic_table.tableConfig[MTDefine.FANGGANGKAICHENGBAO] = fanggangkaichengbaoConfig.get('value', MTDefine.FANGGANGKAICHENGBAO_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting fanggangkaichengbao:', self.logic_table.tableConfig[MTDefine.FANGGANGKAICHENGBAO])

        qianggangchengbaoId = self.initParams.get(MTDefine.QIANGGANGCHENGBAO, 0)
        qianggangchengbaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.QIANGGANGCHENGBAO, qianggangchengbaoId)
        if qianggangchengbaoConfig:
            self.logic_table.tableConfig[MTDefine.QIANGGANGCHENGBAO] = qianggangchengbaoConfig.get('value', MTDefine.QIANGGANGCHENGBAO_YES)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting qianggangchengbao:', self.logic_table.tableConfig[MTDefine.QIANGGANGCHENGBAO])

        maimaId = self.initParams.get(MTDefine.MAIMA, 0)
        maimaConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.MAIMA, maimaId)
        if maimaConfig:
            self.logic_table.tableConfig[MTDefine.MAIMA] = maimaConfig.get('value', MTDefine.MAIMA_ALL)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting maima:', self.logic_table.tableConfig[MTDefine.MAIMA])

        macountId = self.initParams.get(MTDefine.MAIMA_COUNT, 0)
        macountConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.MAIMA_COUNT, macountId)
        if macountConfig:
            self.logic_table.tableConfig[MTDefine.MAIMA_COUNT] = macountConfig.get('value', 1)
            ftlog.debug('MajiangFriendTable.processCreateTableSetting MAIMA_COUNT:',
                        self.logic_table.tableConfig[MTDefine.MAIMA_COUNT])

        winByPaoId = self.initParams.get(MTDefine.WIN_BY_PAO, MTDefine.WIN_BY_ZIMO_NO)
        winByPaoConfig = majiang_conf.getCreateTableConfig(self.gameId, self.playMode, MTDefine.WIN_BY_PAO, winByPaoId)
        if winByPaoConfig:
            winByPao = winByPaoConfig.get('value', 0)
            self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO] = 1 if (winByPao == 0) else 0
            ftlog.debug('MajiangFriendTable.processCreateTableSetting win_by_zimo:', self.logic_table.tableConfig[MTDefine.WIN_BY_ZIMO])

        # 把用户设定的逻辑桌配置传递给 WinRule
        self.logic_table.winRuleMgr.setWinRuleTableConfig(self.logic_table.tableConfig)
        self.logic_table.tableTileMgr.reChooseDealer()
        
    def playerReady(self, seatId, ready):
        beginGame = self.logic_table.playerReady(seatId, ready)
        if beginGame:
            # 纪录上一局的日志 给GM使用
            if len(self.logic_table.tableResult.results) > 0:
                roundResult = self.logic_table.tableResult.results[-1]
                deltaScore = roundResult.score
                totalScore = self.logic_table.tableResult.score
                curRound = self.logic_table.scheduleMgr.curCount - 1
                totalRound = self.logic_table.scheduleMgr.totalCount
                seats = self.logic_table.getSeats()
                ftlog.debug('MajiangFriendTable.nextRoundOrReady nextRound stat tableNo:', self.ftId
                            , 'seats:', seats
                            , 'deltaScore:', deltaScore
                            , 'totalScore:', totalScore
                            , 'gameId:', self.gameId
                            , 'roomId:', self.roomId
                            , 'tableId', self.tableId)
                hall_friend_table.addOneResult(self.ftId, seats, deltaScore, totalScore, curRound, totalRound, self.gameId, self.roomId, self.tableId)
            
            ftlog.debug('MajiangFriendTable.nextRoundOrReady curCount:', self.logic_table.scheduleMgr.curCount)
            if self.logic_table.scheduleMgr.curCount == 1:
                # 纪录开局日志 gameBegin(tableNo, seats, gameId, roomId, tableId)
                seats = self.logic_table.getSeats()
                ftlog.debug('MajiangFriendTable.nextRoundOrReady log game begin tableNo:', self.__ftId
                            , 'seats:', seats
                            , 'gameId:', self.gameId
                            , 'roomId:', self.roomId
                            , 'tableId', self.tableId)
                hall_friend_table.gameBegin(self.__ftId, seats, self.gameId, self.gameId, self.tableId)
            
        return beginGame

    def nextRoundOrReady(self, msg, userId, seatId, action, clientId):
        '''
        table_call next_round
        '''
        self.logic_table.sendMsgTableInfo(seatId)
        self.playerReady(seatId, True)
        self.logic_table.msgProcessor.create_table_succ_response(userId, seatId, 'ready', 1 if (userId == self.__table_owner) else 0)
        for player in self.logic_table.player:
            if not player:
                continue
            
            if (not TYPlayer.isHuman(player.userId)) and (not player.isReady()):
                self.playerReady(player.curSeatId, True)
            
    def resumeFangKa(self, uids):
        if (self.logic_table.scheduleMgr.fangkaCount > 0) and \
                    (not self.getRoomConfig(MTDefine.HAS_ROBOT, 0)):
            itemId = self.room.roomConf.get('create_item', None)
            if itemId:
                consume_fangka_count = self.logic_table.scheduleMgr.fangkaCount
                if self.logic_table.tableConfig.get(MTDefine.SHARE_FANGKA, 0):
                    consume_fangka_count = self.logic_table.tableConfig[MFTDefine.CARD_COUNT] / self.logic_table.playerCount
                    for player in self.players:
                        if not player or player.userId not in uids:
                            continue
                        
                        ftlog.info('MajiangFriendTable.resumeFangKa userId:', player.userId
                                                , ' gameId:', self.gameId
                                                , ' itemId:', itemId
                                                , ' itemCount:', consume_fangka_count
                                                , " table owner:", self.__table_owner
                                                , " roomId:", self.roomId
                                                , " bigRoomId", self.bigRoomId)
                        
                        user_remote.resumeItemFromTable(player.userId
                                        , self.gameId
                                        , itemId
                                        , consume_fangka_count
                                        , self.roomId
                                        , self.tableId
                                        , self.bigRoomId)
                else:
                    if self.tableOwner not in uids:
                        return
                    
                    user_remote.resumeItemFromTable(self.tableOwner
                                        , self.gameId
                                        , itemId
                                        , consume_fangka_count
                                        , self.roomId
                                        , self.tableId
                                        , self.bigRoomId)
            
    def createTableUserLeave(self, msg, userId, seatId, action, clientId):
        '''
        table_call action create_table_user_leave
        '''
        ftlog.debug('MajiangFreiendTable.createTableUserLeave tableOwner:', self.tableOwner)
        if (self.logic_table.isFriendTablePlaying()):
            util.sendPopTipMsg(userId, "游戏已开始，不能解散")
            return
        
        # TODO:房主解散，由前端主动发送，存在隐患，后续修改。房主建房后，掉线，房主的房间状态将不对
        if userId == self.tableOwner:
            ftlog.debug('MajiangFriendTable.create_table_user_leave owner leave...')
            # 解散时，给大家提示
            for player in self.logic_table.player:
                if not player:
                    continue
                # 通知
                util.sendPopTipMsg(player.userId, "房主解散房间")
                
            # 归还剩余房卡道具
            ftlog.debug('MajiangFriendTable.doTableCall leftCardCount:', self.logic_table.scheduleMgr.fangkaCount
                    , ' tableOwner:', self.__table_owner)
            uids = self.logic_table.msgProcessor.getBroadCastUIDs()
            self.resumeFangKa(uids)
            # 解散牌桌
            self.clearTable(True, MUserLeaveReason.FRIEND_TABLE_OWNER_LEAVE)
        else:
            self.resumeFangKa([userId])
            util.sendPopTipMsg(userId, "您已退出房间")
            self.kickOffUser(userId, seatId, True, MUserLeaveReason.FRIEND_TABLE_PLAYER_LEAVE)
     
    def createTableDissolution(self, msg, userId, seatId, action, clientId):
        '''
        table_call action  create_table_dissolution
        '''
        if not self.logic_table.isFriendTablePlaying():
            ftlog.debug('MajiangFriendTable._doTableCall create_table_dissolution game not start, can not dissolved...')
            return
        
        # 投票解散牌桌
        if self.voteHost != MTDefine.INVALID_SEAT:
            ftlog.debug('MajiangFriendTable._doTableCall create_table_dissolution ', self.voteHost, ' already dissolved...')
            return
        
        self.setVoteHost(seatId)
        self.voteInfo[seatId] = {'userId': userId, 'seatId': seatId, 'vote': self.DISSOLVE_AGREE}
        self.setVoteTimeOut(self.getTableConfig('dissolve_vote_time_out', 60))
        ftlog.debug('MajiangFriendTable.create_table_dissolution voteInfo:', self.voteInfo)
        
        # 广播解散投票消息
        self.logic_table.msgProcessor.create_table_dissolve_vote(userId
                    , seatId
                    , self.maxSeatN
                    , self.get_leave_vote_info()
                    , self.get_leave_vote_info_detail()
                    , self.logic_table.player[seatId].name
                    , self.voteTimeOut)
        
    def userLeaveVote(self, msg, userId, seatId, action, clientId):
        '''
        table_call cation user_leave_vote
        '''
        ftlog.debug('MajiangFriendTable.userLeaveVote voteInfo:', self.voteInfo)
        if self.voteHost == MTDefine.INVALID_SEAT:
            ftlog.debug('MajiangFriendTable._doTableCall user_leave_vote, voteHost is invalid, no need process this message...')
            return
        
        vote = msg.getParam('vote', self.DISSOLVE_REFUSE)
        self.voteInfo[seatId] = {'userId': userId, 'seatId': seatId, 'vote': vote}
        self.logic_table.msgProcessor.create_table_dissolve_vote(userId
                    , seatId
                    , self.maxSeatN
                    , self.get_leave_vote_info()
                    , self.get_leave_vote_info_detail()
                    , self.logic_table.player[self.voteHost].name
                    , self.voteTimeOut)
        # 计算投票结果
        self.dissolveDecision()
        
    def createFriendInvite(self, msg, userId, seatId, action, clientId):
        '''
        table_call action create_friend_invite
        '''
        if self.gameId == 715:
            # 临时硬编码，对卡五星分享的内容做特殊定制
            contentArr = []
            for i in range(len(self.paramsOptionName)):
                if self.paramsOptionName[i] != "人数":
                    contentArr.append(self._params_desc[i])
            contentStr = ', '.join(contentArr)
        else:
            contentStr = '、'.join(self._params_desc)
        util.sendTableInviteShareTodoTask(userId
                , self.gameId
                , self.ftId
                , self.playMode
                , self.logic_table.scheduleMgr.curCount
                , contentStr)
         
    
    def _doTableCall(self, msg, userId, seatId, action, clientId):
        """
        继承父类，处理table_call消息
        单独处理自建桌的分享/解散
        """
        if not self.CheckSeatId(seatId, userId):
            ftlog.warn("MajiangFriendTable.doTableCall, delay msg action:", action
                    , ' seatId:', seatId
                    , ' messange:', msg)
            return
            
        if action == 'next_round':
            if self.logic_table.isPlaying():
                return
            if self.room.runStatus != TYRoom.ROOM_STATUS_RUN:
                util.sendPopTipMsg(userId, "亲爱的玩家服务即将例行维护，请5分钟后继续打牌，给您带来的不便尽请谅解！")
                return
            self.nextRoundOrReady(msg, userId, seatId, action, clientId)
                
        elif action == 'ready':
            if self.logic_table.isPlaying():
                return
            self.nextRoundOrReady(msg, userId, seatId, action, clientId)
            
        elif action == 'create_table_user_leave':
            self.createTableUserLeave(msg, userId, seatId, action, clientId)
            
        elif action == 'create_table_dissolution':
            self.createTableDissolution(msg, userId, seatId, action, clientId)
            
        elif action == 'user_leave_vote':
            self.userLeaveVote(msg, userId, seatId, action, clientId)
                
        elif action == 'create_friend_invite':  # 微信邀请todotask下发
            self.createFriendInvite(msg, userId, seatId, action, clientId)
            
        elif action == 'friend_table_ready_time_out':  # 准备超时，回收牌桌
            # 退还房卡
            uids = self.logic_table.msgProcessor.getBroadCastUIDs()
            self.resumeFangKa(uids)
            self.clearTable(True, MUserLeaveReason.READY_TIME_OUT)
            #===================================================================
            # # 通用提示框提示前端
            # for userId in uids:
            #     Majiang2Util.sendShowInfoTodoTask(userId, self.gameId
            #             ,'缺角打不起来，约好好友再来开房吧！房间将被关闭，开房卡将被退回。')
            #===================================================================
            
        elif action == 'leave':  # 离开
            pass
        else:
            super(MajiangFriendTable, self)._doTableCall(msg, userId, seatId, action, clientId)
            
    def _doStandUp(self, msg, userId, seatId, reason, clientId):
        '''
        自建桌这里的逻辑退出，不自动站起/退出
        '''
        pass
    
    def handler_table_manager_not_play(self):
        '''
        牌桌状态管理器，由于牌桌状态会实时变化，所以不能保存牌桌状态
        --> 没有真人，清空桌子，取消定时器
        --> 有真人
            --> 有人准备
                --> 人满，玩家超时踢出未准备的玩家 回到第一步
                --> 人不满 添加机器人 会到第一步
        '''
        ftlog.debug('MajiangFriendTable.handler_table_manager_not_play tableId:', self.tableId)
        # 桌子上没有真人，则清理桌子
        if ((self.realPlayerNum >= 0) and (self.playersNum == 0)) or (self.realPlayerNum == 0):
            ftlog.debug("MajiangFriendTable.handler_table_manager_not_play clearTable...")
            self.clearTable(True, MUserLeaveReason.IS_ROBOT)
            return 
        
        # 桌子上有人准备，根据情况添加机器人
        hasReady = False 
        for player in self.logic_table.players:
            if player and player.isReady():
                hasReady = True 
                break
        robotMode = self.getRoomConfig(MTDefine.HAS_ROBOT, 1)
        if hasReady:
            if self.realPlayerNum < self.maxSeatN and robotMode == 1:
                if self.addRobotInterval == -1:
                    # 初始化 随机时间
                    robot_interval = majiang_conf.getRobotInterval(self.gameId)
                    if robot_interval >= 3:
                        randTime = random.randint(0, 2) - 1
                        robot_interval += randTime
                    self.setAddRobotInterval(robot_interval)
                    
                if self.addRobotInterval == 0:
                    robotMode = self.getRoomConfig(MTDefine.HAS_ROBOT, 1)
                    if robotMode != 1:
                        return
                    
                    robotRandom = self._randRobotUserId()
                    ftlog.debug('MajiangFriendTable.handler_table_manager_not_play robotRandom:', robotRandom)
                    from majiang2.resource import resource
                    robot = resource.getRobot(robotRandom)
                    self.doSitDown(robot['userId'], -1, None, 'robot_3.7_-hall6-robot')
                    # 设置时间为默认值
                    self.setAddRobotInterval(-1)
                elif self.addRobotInterval > 0:
                    self.setAddRobotInterval(self.addRobotInterval - MTDefine.TABLE_TIMER)
                    ftlog.debug('MajiangFriendTable.handler_table_manager_not_play addRobotInterval:', self.addRobotInterval)
        
        # 在牌局未开始过程中，也可以解散牌桌
        if self.voteHost != MTDefine.INVALID_SEAT:
            self.__vote_time_out -= MTDefine.TABLE_TIMER
            ftlog.debug('MajiangFriendTable.handle_auto_decide_action voteTimeOut ', self.voteTimeOut)
            for player in self.logic_table.player:
                if not player:
                    continue
                if not self.voteInfo[player.curSeatId] and player.isRobot():
                    self.__vote_info[player.curSeatId] = {'userId': player.userId, 'seatId': player.curSeatId, 'vote': self.DISSOLVE_AGREE}
                    self.logic_table.msgProcessor.create_table_dissolve_vote(player.userId
                        , player.curSeatId
                        , self.maxSeatN
                        , self.get_leave_vote_info()
                        , self.get_leave_vote_info_detail()
                        , self.logic_table.player[self.voteHost].name
                        , self.__vote_time_out)
                    self.dissolveDecision()
                    break

            if self.voteTimeOut <= 0:
                self.processVoteDissolveTimeOut()
                  
                    
                
    def handle_auto_decide_action(self):
        """牌桌定时器"""
        if self.__ready_time_out_timer and self.logic_table.isFriendTablePlaying():
            self.__ready_time_out_timer = False
            self.tableTimer.cancelTimer(self.tableOwnerSeatId)
        
        ftlog.debug('MajiangFriendTable.handle_auto_decide_action voteHost:', self.voteHost)
        
        if self.voteHost != MTDefine.INVALID_SEAT:
            self.__vote_time_out -= MTDefine.TABLE_TIMER
            ftlog.debug('MajiangFriendTable.handle_auto_decide_action voteTimeOut ', self.voteTimeOut)
            for player in self.logic_table.player:
                if not player:
                    continue
                if not self.voteInfo[player.curSeatId] and player.isRobot():
                    self.__vote_info[player.curSeatId] = {'userId': player.userId, 'seatId': player.curSeatId, 'vote': self.DISSOLVE_AGREE}
                    self.logic_table.msgProcessor.create_table_dissolve_vote(player.userId
                        , player.curSeatId
                        , self.maxSeatN
                        , self.get_leave_vote_info()
                        , self.get_leave_vote_info_detail()
                        , self.logic_table.player[self.voteHost].name
                        , self.__vote_time_out)
                    self.dissolveDecision()
                    break

            if self.voteTimeOut <= 0:
                self.processVoteDissolveTimeOut()
                
        if self.logic_table.isGameOver():
            """游戏结束，通知玩家离开，站起，重置牌桌"""
            ftlog.debug('MajiangFriendTable.handle_auto_decide_action gameOver... tableId:', self.tableId
                    , ' totalRoundCount:', self.logic_table.scheduleMgr.totalCount
                    , ' now RoundCount:', self.logic_table.scheduleMgr.curCount)
            
            # 如果，表示按局数最终结算，否则按圈数结算
            ftlog.debug('useQuan:', 1,
                        'curRountCount:', self.logic_table.scheduleMgr.curCount,
                        'totalRoundCount:', self.logic_table.scheduleMgr.totalCount,
                        'curCircleCount', self.logic_table.scheduleMgr.curQuan,
                        'totalCircleCount', self.logic_table.scheduleMgr.totalQuan)
            
            if self.logic_table.scheduleMgr.isOver():
                self.logic_table.sendCreateExtendBudgetsInfo(0)
                ftlog.debug('MajiangFriendTable.handle_auto_decide_action cur Table hasRobot:', self.getRoomConfig(MTDefine.HAS_ROBOT, 0))    
                if not self.getRoomConfig(MTDefine.HAS_ROBOT, 0):
                    self.saveRecordAfterTable()
                self.clearTable(False, MUserLeaveReason.GAME_OVER)
                return

            self.logic_table.nextRound()
            self.resetNoOptionTimeOut()
            return
        
        self.actionHander.updateTimeOut(-MTDefine.TABLE_TIMER)
        self.actionHander.doAutoAction()
        self.checkNoOptionTimeOut()

    def resetNoOptionTimeOut(self):
        """充值无操作超时参数"""
        if self.__cur_no_option_time_out != -1:
            self.__cur_no_option_time_out = -1
            self.__cur_seat = 0
        
    def checkNoOptionTimeOut(self):
        """检查无操作超时"""
        if not self.getRoomConfig(MTDefine.HAS_ROBOT, 0):
            """非练习场不检查"""
            return
        
        if not self.logic_table.isFriendTablePlaying():
            """牌桌不是玩牌状态，不检查"""
            return
        
        nowSeat = self.logic_table.curSeat
        ftlog.debug('MajiangFriendTable.checkNoOptionTimeOut timeOut:', self.curNoOptionTimeOut
                , ' curSeat:', self.curSeat
                , ' ftOwner:', self.tableOwner
                , ' tableId:', self.tableId
                , ' nowSeat:', nowSeat)
        if (self.curNoOptionTimeOut == -1) or (self.curSeat != nowSeat):
            self.__cur_no_option_time_out = self.logic_table.getTableConfig(MFTDefine.CLEAR_TABLE_NO_OPTION_TIMEOUT, 3600)
            self.__cur_seat = nowSeat
        elif self.curNoOptionTimeOut > 0:
            self.__cur_no_option_time_out -= 1
            if self.curNoOptionTimeOut <= 0:
                self.resetNoOptionTimeOut()
                self.clearTable(True, MUserLeaveReason.NO_OPTION_TIME_OUT)
        
    def processVoteDissolveTimeOut(self):
        """超时自动处理解散投票"""
        ftlog.debug('MajiangFriendTable.processVoteDissolveTimeOut...')
        for player in self.logic_table.player:
            if not player:
                continue
            
            if not self.voteInfo[player.curSeatId]:
                self.__vote_info[player.curSeatId] = {'userId': player.userId, 'seatId': player.curSeatId, 'vote': self.DISSOLVE_AGREE}
        self.dissolveDecision()
        
    def resetVoteInfo(self):
        self.__vote_host = MTDefine.INVALID_SEAT
        self.__vote_info = [None for _ in range(self.maxSeatN)]
        self.__vote_time_out = 0
    
    def dissolveDecision(self):
        """计算投票结果"""
        ftlog.debug('MajiangFriendTable.dissolveDecision voteInfo:', self.voteInfo)
        
        agree = 0
        refuse = 0
        for info in self.voteInfo:
            if not info:
                continue
            
            if info['vote'] == self.DISSOLVE_AGREE:
                agree += 1
            if info['vote'] == self.DISSOLVE_REFUSE:
                refuse += 1
        
        ftlog.debug('MajiangFriendTable.dissolveDecision refuse:', refuse)
        bClear = False
        # 新增投票规则
        # 如果设置REFUSE_LEAVE_VOTE_NUM 当投拒绝票数>=设定数则本局继续
        refuseVoteConfig = self.getTableConfig(MFTDefine.REFUSE_LEAVE_VOTE_NUM, {})
        ftlog.debug('MajiangFriendTable.dissolveDecision voteConfig:', refuseVoteConfig)
        strCount = str(self.logic_table.playerCount)
        refuseCount = refuseVoteConfig.get(strCount, 1)
        ftlog.debug('MajiangFriendTable.dissolveDecision refuse:', refuseCount, refuse)
        if refuse >= refuseCount:
            for player in self.logic_table.player:
                if not player:
                    continue
                util.sendPopTipMsg(player.userId, "经投票，牌桌继续...")
                self.logic_table.msgProcessor.create_table_dissolve_close_vote(player.userId, player.curSeatId)
            self.resetVoteInfo()
            return
        
        if agree > self.maxSeatN - refuseCount:
            bClear = True
        else:
            # 等待投票结果或者超时
            return
        
        if bClear:
            self.logic_table.setVoteHost(self.voteHost)
            self.resetVoteInfo()
            # 解散牌桌时发送大结算
            self.logic_table.sendCreateExtendBudgetsInfo(1)
            
            ftlog.debug('MajiangFriendTable.dissolveDecision cur Table hasRobot:', self.getRoomConfig(MTDefine.HAS_ROBOT, 0))
            if not self.getRoomConfig(MTDefine.HAS_ROBOT, 0):
                self.saveRecordAfterTable()
            
            # 归还剩余房卡道具
            if self.logic_table.tableConfig.get(MTDefine.RESUME_ITEM_AFTER_BEGIN, 1):
                uids = self.logic_table.msgProcessor.getBroadCastUIDs()
                self.resumeFangKa(uids)
            # 通知玩家离开
            for player in self.logic_table.player:
                if not player:
                    continue
                
                util.sendPopTipMsg(player.userId, "经投票，牌桌已解散")
                self.logic_table.msgProcessor.create_table_dissolve_close_vote(player.userId, player.curSeatId, True)
                
            # 牌桌解散
            self.clearTable(False, MUserLeaveReason.FRIEND_TABLE_DISSOLVE)
 
    def get_leave_vote_info(self):
        """获取投票简要信息"""
        agree = 0
        disagree = 0
        for info in self.voteInfo:
            if not info:
                continue
            
            if info['vote'] == self.DISSOLVE_AGREE:
                agree += 1
            elif info['vote'] == self.DISSOLVE_REFUSE:
                disagree += 1
        return {'disagree': disagree, 'agree':agree}
    
    def get_leave_vote_info_detail(self):
        '''20160909新需求添加，增加用户头像,用户名等信息'''
        retList = []
        for info in self.voteInfo:
            if not info:
                continue
            
            retData = {}
            seatId = info['seatId']
            retData['name'], retData['purl'] = self.logic_table.player[seatId].name, self.logic_table.player[seatId].purl
            retData['vote'] = info['vote']
            retData['userId'] = info['userId']
            retList.append(retData) 
        return retList
    
    def clearTable(self, sendLeave, reason='clearTable'):
        # 纪录最后一局日志和结束日志 
        seats = self.logic_table.getSeats()
        if self.logic_table.scheduleMgr.isOver():
            if len(self.logic_table.tableResult.results) > 0:
                roundResult = self.logic_table.tableResult.results[-1]
                deltaScore = roundResult.score
                totalScore = self.logic_table.tableResult.score
                curRound = self.logic_table.scheduleMgr.curCount
                totalRound = self.logic_table.scheduleMgr.totalCount
                ftlog.debug('MajiangFriendTable.cleraTable stat tableNo', self.ftId, 'seats', seats, 'deltaScore:',
                            deltaScore, 'totalScore:', totalScore, 'gameId:', self.gameId, 'roomId:', self.roomId, 'tableId', self.tableId)
                hall_friend_table.addOneResult(self.ftId, seats, deltaScore, totalScore, curRound, totalRound, self.gameId, self.roomId, self.tableId)
            else:
                ftlog.debug('MajiangFriendTable.cleraTable curRoundCount:',
                            self.logic_table.scheduleMgr.curCount,
                            'totalRoundCount:',
                            self.logic_table.scheduleMgr.totalCount)
        
        totalScore = self.logic_table.tableResult.score
        if not totalScore:
            totalScore = [0 for _ in range(self.logic_table.playerCount)]
        totalRound = self.logic_table.scheduleMgr.totalCount
        ftlog.debug('MajiangFriendTable.cleraTable stat gameEnd tableNo:', self.ftId
                    , 'seats:', seats
                    , 'totalScore:', totalScore
                    , 'totalRound:', totalRound
                    , 'gameId:', self.gameId
                    , 'roomId:', self.roomId
                    , 'tableId:', self.tableId)
        hall_friend_table.gameEnd(self.ftId, seats, totalScore, totalRound, self.gameId, self.roomId, self.tableId)
        
        """清理桌子"""
        super(MajiangFriendTable, self).clearTable(sendLeave, reason)
        # 释放大厅房间ID
        hall_friend_table.releaseFriendTable(self.gameId, self.ftId)
        CreateTableData.removeCreateTableNo(gdata.serverId(), self.ftId)
