"""
扣分规则模块 (Discount)
根据外部信号（如脚手架介入等级）计算扣分系数，并应用到最终分数。
支持多维度扣分、分层干预、难度加权、加分恢复、连续干预暂停等复杂逻辑。
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple, Union


class Discount:
    """
    扣分规则引擎
    管理四个核心维度（监控、规划、应变、评估）的分数，根据干预事件动态调整。
    """

    # 维度常量
    DIM_MONITOR = 'monitor'
    DIM_PLAN = 'plan'
    DIM_ADAPT = 'adapt'
    DIM_EVALUATE = 'evaluate'
    ALL_DIMENSIONS = [DIM_MONITOR, DIM_PLAN, DIM_ADAPT, DIM_EVALUATE]

    # 事件类型常量
    EVT_LONG_SILENCE = 'long_silence'
    EVT_DEAD_LOOP = 'dead_loop'
    EVT_PATH_DEVIATION = 'path_deviation'
    EVT_KEYWORD_TRIGGER = 'keyword_trigger'
    ALL_EVENTS = [EVT_LONG_SILENCE, EVT_DEAD_LOOP, EVT_PATH_DEVIATION, EVT_KEYWORD_TRIGGER]

    # 干预等级常量
    LVL_L1 = 'L1'
    LVL_L2 = 'L2'
    LVL_L3 = 'L3'
    ALL_LEVELS = [LVL_L1, LVL_L2, LVL_L3]

    def __init__(self, initial_scores: Optional[Dict[str, float]] = None):
        """
        初始化扣分模块
        :param initial_scores: 各维度初始分数，默认为10.0
        """
        # 各维度当前分数
        self.scores = {dim: 10.0 for dim in self.ALL_DIMENSIONS}
        if initial_scores:
            for dim, val in initial_scores.items():
                if dim in self.ALL_DIMENSIONS:
                    self.scores[dim] = val

        # 难度，影响扣分权重：easy *1.2, hard *0.8, normal *1.0
        self.difficulty = 'normal'  # 'easy', 'hard', 'normal'

        # 事件历史计数（用于判断首次/重复等）
        self.event_count = {evt: 0 for evt in self.ALL_EVENTS}

        # 最近干预时间戳和连续干预计数
        self.last_intervention_time: Optional[float] = None
        self.consecutive_interventions = 0
        self.paused_until: Optional[float] = None  # 暂停截止时间

        # 待处理的L1干预（用于30秒自我纠正）
        self.pending_l1: Dict[str, dict] = {}  # id -> {timestamp, category}

        # 维度上限标记（L3干预后该维度上限为2分）
        self.dimension_caps: Dict[str, float] = {dim: float('inf') for dim in self.ALL_DIMENSIONS}

        # L3干预次数记录（用于多次L3扣评估指数）
        self.l3_count = 0

    # ==================== 公共方法 ====================

    def set_difficulty(self, difficulty: str):
        """设置当前题目难度"""
        if difficulty in ['easy', 'hard', 'normal']:
            self.difficulty = difficulty

    def get_scores(self) -> Dict[str, float]:
        """获取当前各维度分数"""
        return self.scores.copy()

    def get_final_score(self) -> float:
        """获取最终总分（各维度分数之和）"""
        return sum(self.scores.values())

    def apply_intervention(self, level: str, category: str, timestamp: float, **kwargs) -> Optional[str]:
        """
        应用干预事件
        :param level: 干预等级 L1/L2/L3
        :param category: 事件类型（如 long_silence）
        :param timestamp: 当前时间戳（秒）
        :param kwargs: 额外参数
            - is_first: bool (仅当需要覆盖历史判断时使用)
            - is_repeat: bool
            - accepted: bool (L2时是否接受启发)
            - upgraded_from_id: str (如果是升级自某个L1干预，传入其ID)
            - dimension: str (可选，指定主要影响的维度，否则自动推断)
            - need_upgrade_to_L3: bool (L2是否需要升级到L3)
            - failed_after_L3: bool (L3后仍无法纠正)
        :return: 如果是L1干预，返回一个待处理ID，用于后续自我纠正或升级；否则返回None
        """
        # 先检查并处理超时的待处理L1
        self._check_pending_timeout(timestamp)

        # 检查是否在暂停期
        if self._is_paused(timestamp):
            return None

        # 更新连续干预状态
        self._update_consecutive_interventions(timestamp)

        # 根据等级分发处理
        if level == self.LVL_L1:
            return self._handle_l1_intervention(category, timestamp, kwargs)
        elif level == self.LVL_L2:
            self._handle_l2_intervention(category, timestamp, kwargs)
        elif level == self.LVL_L3:
            self._handle_l3_intervention(category, timestamp, kwargs)
        else:
            raise ValueError(f"Unknown intervention level: {level}")

        return None

    def apply_self_correct(self, intervention_id: str, timestamp: float, is_active: bool = True, dimension: Optional[str] = None):
        """
        应用自我纠正（针对L1干预）
        :param intervention_id: 对应的L1干预ID
        :param timestamp: 当前时间戳
        :param is_active: 是否为主动自我纠正（主动有加分，提醒后调整无加分）
        :param dimension: 影响的维度，若为None则根据事件类别推断
        """
        self._check_pending_timeout(timestamp)

        if intervention_id not in self.pending_l1:
            # 可能已超时处理或ID无效
            return

        pending = self.pending_l1[intervention_id]
        time_diff = timestamp - pending['timestamp']
        category = pending['category']

        if time_diff <= 30.0:
            # 30秒内纠正，不扣分
            del self.pending_l1[intervention_id]
            if is_active:
                # 主动自我纠正：对应维度 +0.3
                dim = dimension or self._get_default_dimension(category)
                self._add_score(dim, 0.3)
        else:
            # 超过30秒，应已超时处理，但以防万一，这里也处理
            self._apply_base_penalty(category, timestamp, is_escalated=False)
            del self.pending_l1[intervention_id]

    def apply_positive_event(self, event_type: str, dimension: Optional[str] = None, **kwargs):
        """
        应用加分事件（恢复分数）
        :param event_type: 事件类型，可选：
            'self_correct'      -> 主动自我纠正（已单独处理）
            'cite_previous'     -> 引用先前启发：应变 +0.5
            'predict_problem'   -> 预判潜在问题：规划 +0.5
            'verify_conclusion' -> 验证自身结论：评估 +0.3
            'late_reduce'       -> 后半程干预减少：应变 +0.5
            'repeat_reduce'     -> 重复错误减少：监控 +0.3
        :param dimension: 可指定维度，否则按默认
        """
        mapping = {
            'cite_previous': (self.DIM_ADAPT, 0.5),
            'predict_problem': (self.DIM_PLAN, 0.5),
            'verify_conclusion': (self.DIM_EVALUATE, 0.3),
            'late_reduce': (self.DIM_ADAPT, 0.5),
            'repeat_reduce': (self.DIM_MONITOR, 0.3),
        }
        if event_type in mapping:
            default_dim, value = mapping[event_type]
            dim = dimension or default_dim
            self._add_score(dim, value)

    # ==================== 内部处理方法 ====================

    def _handle_l1_intervention(self, category: str, timestamp: float, kwargs: dict) -> str:
        """处理L1干预：创建待处理记录，返回ID"""
        # 检查是否有升级来源（一般L1没有升级来源）
        upgraded_from = kwargs.get('upgraded_from_id')
        if upgraded_from:
            # 如果是升级自某事件，则按基础表扣分（实际上升级到L2应走L2处理，此处仅作安全）
            self._apply_base_penalty(category, timestamp, is_escalated=False)
            return None

        # 生成唯一ID
        pid = str(uuid.uuid4())
        self.pending_l1[pid] = {
            'timestamp': timestamp,
            'category': category,
        }
        return pid

    def _handle_l2_intervention(self, category: str, timestamp: float, kwargs: dict):
        """处理L2干预"""
        accepted = kwargs.get('accepted', False)  # 是否接受启发
        upgraded_from = kwargs.get('upgraded_from_id')
        dimension = kwargs.get('dimension')

        # 如果是由L1升级而来，先移除对应的待处理项
        if upgraded_from and upgraded_from in self.pending_l1:
            del self.pending_l1[upgraded_from]

        # 确定本次干预对应的维度（根据事件类别和历史次数）
        if dimension is None:
            dimension = self._get_dimension_for_event(category)

        # 基础扣分（根据接受与否）
        if accepted:
            delta = -0.5
        else:
            delta = -1.5

        self._apply_penalty(dimension, delta)

        # 如果需要升级到L3，额外扣0.5
        if kwargs.get('need_upgrade_to_L3'):
            self._apply_penalty(dimension, -0.5)

    def _handle_l3_intervention(self, category: str, timestamp: float, kwargs: dict):
        """处理L3干预"""
        dimension = kwargs.get('dimension')
        if dimension is None:
            dimension = self._get_dimension_for_event(category)

        # L3干预：该维度上限设为2分
        self.dimension_caps[dimension] = 2.0
        if self.scores[dimension] > 2.0:
            self.scores[dimension] = 2.0

        # 多次L3干预：评估指数同步扣分（每次-0.5）
        self.l3_count += 1
        self._apply_penalty(self.DIM_EVALUATE, -0.5)

        # 如果L3后仍无法纠正，则维度分数降至0~1分（这里取1分）
        if kwargs.get('failed_after_L3'):
            self.scores[dimension] = min(self.scores[dimension], 1.0)

    def _apply_base_penalty(self, category: str, timestamp: float, is_escalated: bool = False):
        """
        根据基础触发扣分表扣分（用于无分层干预或升级时）
        :param category: 事件类型
        :param timestamp: 时间戳（用于记录历史）
        :param is_escalated: 是否为后续升级（针对keyword_trigger）
        """
        # 更新事件计数
        self.event_count[category] += 1
        count = self.event_count[category]

        # 根据事件类型和次数决定扣分
        if category == self.EVT_LONG_SILENCE:
            if count == 1:
                dim = self.DIM_MONITOR
                delta = -0.5
            else:
                dim = self.DIM_PLAN
                delta = -0.5
        elif category == self.EVT_DEAD_LOOP:
            if count == 1:
                dim = self.DIM_MONITOR
                delta = -1.0
            elif count == 2:
                dim = self.DIM_ADAPT
                delta = -0.5
            else:
                # 超过两次如何处理？这里按第二次继续扣？暂时不处理
                return
        elif category == self.EVT_PATH_DEVIATION:
            dim = self.DIM_PLAN
            delta = -1.0
        elif category == self.EVT_KEYWORD_TRIGGER:
            if is_escalated:
                dim = self.DIM_MONITOR
                delta = -0.5
            else:
                # 首次触发
                if count == 1:
                    dim = self.DIM_ADAPT
                    delta = -0.5
                else:
                    # 后续升级？如果未升级但重复触发，可能也按首次？这里按首次处理
                    dim = self.DIM_ADAPT
                    delta = -0.5
        else:
            return

        self._apply_penalty(dim, delta)

    def _apply_penalty(self, dimension: str, delta: float):
        """应用扣分（考虑难度加权和维度上限）"""
        # 难度加权（仅对扣分，即delta<0）
        if delta < 0:
            if self.difficulty == 'easy':
                delta *= 1.2
            elif self.difficulty == 'hard':
                delta *= 0.8

        new_score = self.scores[dimension] + delta
        # 应用维度上限（如果有）
        cap = self.dimension_caps[dimension]
        if new_score > cap:
            new_score = cap
        self.scores[dimension] = max(0, new_score)  # 不低于0分

    def _add_score(self, dimension: str, delta: float):
        """加分（不考虑难度加权，但受上限约束）"""
        new_score = self.scores[dimension] + delta
        cap = self.dimension_caps[dimension]
        if new_score > cap:
            new_score = cap
        self.scores[dimension] = max(0, new_score)

    def _get_dimension_for_event(self, category: str) -> str:
        """根据事件类型和当前历史返回默认影响维度（用于L2/L3）"""
        # 简单映射：根据事件和已发生次数
        count = self.event_count[category] + 1  # 加1因为还没扣分
        if category == self.EVT_LONG_SILENCE:
            return self.DIM_MONITOR if count == 1 else self.DIM_PLAN
        elif category == self.EVT_DEAD_LOOP:
            return self.DIM_MONITOR if count == 1 else self.DIM_ADAPT
        elif category == self.EVT_PATH_DEVIATION:
            return self.DIM_PLAN
        elif category == self.EVT_KEYWORD_TRIGGER:
            return self.DIM_ADAPT  # 首次，后续升级可能不同，但由外部指定
        else:
            return self.DIM_MONITOR

    def _get_default_dimension(self, category: str) -> str:
        """获取默认维度（用于自我纠正加分）"""
        mapping = {
            self.EVT_LONG_SILENCE: self.DIM_MONITOR,
            self.EVT_DEAD_LOOP: self.DIM_MONITOR,
            self.EVT_PATH_DEVIATION: self.DIM_PLAN,
            self.EVT_KEYWORD_TRIGGER: self.DIM_ADAPT,
        }
        return mapping.get(category, self.DIM_MONITOR)

    def _check_pending_timeout(self, now: float):
        """检查并处理超时的待处理L1干预（超过30秒）"""
        timeout_ids = []
        for pid, info in self.pending_l1.items():
            if now - info['timestamp'] > 30.0:
                # 超时，按基础表扣分
                self._apply_base_penalty(info['category'], info['timestamp'], is_escalated=False)
                timeout_ids.append(pid)
        for pid in timeout_ids:
            del self.pending_l1[pid]

    def _is_paused(self, timestamp: float) -> bool:
        """检查当前是否处于暂停期（暂停期间不处理任何干预扣分）"""
        if self.paused_until and timestamp < self.paused_until:
            return True
        # 暂停结束，清除状态
        if self.paused_until and timestamp >= self.paused_until:
            self.paused_until = None
            self.consecutive_interventions = 0
        return False

    def _update_consecutive_interventions(self, timestamp: float):
        """更新连续干预计数，并在达到3次时设置暂停"""
        if self.last_intervention_time is None:
            self.consecutive_interventions = 1
        else:
            time_diff = timestamp - self.last_intervention_time
            if time_diff <= 60.0:  # 60秒内算连续
                self.consecutive_interventions += 1
            else:
                self.consecutive_interventions = 1

        self.last_intervention_time = timestamp

        # 如果连续达到3次，设置暂停60秒
        if self.consecutive_interventions >= 3:
            self.paused_until = timestamp + 60.0
            self.consecutive_interventions = 0  # 重置，暂停结束后重新计数