import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

class PromptTemplate:
    """Prompt模板类，包含模板内容、变量和版本信息"""
    
    def __init__(self, template_id: str, name: str, content: str, 
                 description: str = "", variables: List[str] = None,
                 version: str = "1.0.0", created_at: datetime = None):
        """
        初始化Prompt模板
        
        Args:
            template_id: 模板唯一标识
            name: 模板名称
            content: 模板内容（包含变量占位符，如{{var_name}}）
            description: 模板描述
            variables: 模板中定义的变量列表（自动提取或手动指定）
            version: 版本号，建议遵循语义化版本
            created_at: 创建时间
        """
        self.template_id = template_id
        self.name = name
        self.content = content
        self.description = description
        self.variables = variables or self._extract_variables(content)
        self.version = version
        self.created_at = created_at or datetime.now()
    
    def _extract_variables(self, content: str) -> List[str]:
        """从模板内容中提取变量占位符（格式：{{var_name}}）"""
        pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
        return list(set(re.findall(pattern, content)))
    
    def render(self, **kwargs) -> str:
        """
        渲染模板，替换变量
        
        Args:
            **kwargs: 变量名到值的映射
        
        Returns:
            渲染后的字符串
        
        Raises:
            KeyError: 如果缺少必需的变量
        """
        missing = [var for var in self.variables if var not in kwargs]
        if missing:
            raise KeyError(f"缺少必需的变量: {', '.join(missing)}")
        
        result = self.content
        for var, value in kwargs.items():
            # 处理复杂类型的变量（如列表、字典）为JSON字符串
            if not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
            result = result.replace(f'{{{{{var}}}}}', value)
        return result
    
    def to_dict(self) -> Dict:
        """转换为字典，便于序列化"""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "variables": self.variables,
            "version": self.version,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PromptTemplate':
        """从字典恢复模板对象"""
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class PromptTemplateManager:
    """Prompt模板管理器，支持多模板、版本管理"""
    
    def __init__(self, storage: Dict[str, List[PromptTemplate]] = None):
        """
        初始化管理器
        
        Args:
            storage: 存储结构，键为模板ID，值为按版本降序排列的模板列表
        """
        self._storage: Dict[str, List[PromptTemplate]] = storage or {}
    
    def add_template(self, template: PromptTemplate, 
                     update_if_exists: bool = False) -> bool:
        """
        添加新模板或新版本
        
        Args:
            template: 模板对象
            update_if_exists: 如果模板ID已存在，是否作为新版本添加；否则覆盖
        
        Returns:
            bool: 是否成功添加
        """
        template_id = template.template_id
        if template_id not in self._storage:
            self._storage[template_id] = [template]
            return True
        
        # 检查版本是否已存在
        existing_versions = [t.version for t in self._storage[template_id]]
        if template.version in existing_versions:
            if update_if_exists:
                # 替换同版本（通常用于修复）
                self._storage[template_id] = [
                    t if t.version != template.version else template 
                    for t in self._storage[template_id]
                ]
                return True
            else:
                return False  # 版本已存在，不添加
        
        # 添加新版本并保持降序排列
        self._storage[template_id].append(template)
        self._storage[template_id].sort(
            key=lambda t: self._version_to_tuple(t.version), 
            reverse=True
        )
        return True
    
    def get_template(self, template_id: str, 
                     version: Optional[str] = None) -> Optional[PromptTemplate]:
        """
        获取指定版本的模板，若version为None则返回最新版本
        
        Args:
            template_id: 模板ID
            version: 版本号，None表示最新
        
        Returns:
            PromptTemplate或None
        """
        if template_id not in self._storage:
            return None
        
        versions = self._storage[template_id]
        if version is None:
            return versions[0]  # 最新版本（已排序）
        
        for t in versions:
            if t.version == version:
                return t
        return None
    
    def list_templates(self) -> List[Dict]:
        """列出所有模板的摘要信息（不含内容）"""
        result = []
        for template_id, versions in self._storage.items():
            latest = versions[0]
            result.append({
                "template_id": template_id,
                "name": latest.name,
                "description": latest.description,
                "latest_version": latest.version,
                "versions": [v.version for v in versions],
                "variables": latest.variables
            })
        return result
    
    def delete_template(self, template_id: str, version: Optional[str] = None) -> bool:
        """
        删除模板的特定版本或整个模板
        
        Args:
            template_id: 模板ID
            version: 版本号，若为None则删除整个模板
        
        Returns:
            bool: 是否成功删除
        """
        if template_id not in self._storage:
            return False
        
        if version is None:
            del self._storage[template_id]
            return True
        
        versions = self._storage[template_id]
        new_versions = [t for t in versions if t.version != version]
        if len(new_versions) == len(versions):
            return False  # 版本不存在
        elif new_versions:
            self._storage[template_id] = new_versions
        else:
            del self._storage[template_id]  # 删除最后一个版本后移除模板
        return True
    
    def _version_to_tuple(self, version: str) -> tuple:
        """将版本字符串转换为可比较的元组"""
        parts = version.split('.')
        # 补全到三位，缺失部分用0代替
        while len(parts) < 3:
            parts.append('0')
        return tuple(int(p) if p.isdigit() else p for p in parts)
    
    def save_to_file(self, filepath: str):
        """将管理器状态保存到JSON文件"""
        data = {
            template_id: [t.to_dict() for t in versions]
            for template_id, versions in self._storage.items()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, filepath: str):
        """从JSON文件加载管理器状态"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self._storage = {}
        for template_id, templates_data in data.items():
            versions = [PromptTemplate.from_dict(td) for td in templates_data]
            # 确保按版本排序

def load_templates_from_config(config_path: str) -> PromptTemplateManager:
    """从JSON配置文件加载模板，返回初始化好的管理器实例"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    manager = PromptTemplateManager()
    for template_id, versions_data in config.items():
        for data in versions_data:
            if "created_at" not in data:
                data["created_at"] = datetime.now()
            else:
                data["created_at"] = datetime.fromisoformat(data["created_at"])
            template = PromptTemplate(**data)
            manager.add_template(template, update_if_exists=True)
    return manager