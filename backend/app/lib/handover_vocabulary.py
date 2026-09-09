"""
點交照片辨識詞彙表(權威白名單)

**這份表是從 jgb2 抄過來的,不是我們自己定的。** 來源是 Laravel 端
`app/Estate.php` 的三個靜態方法:

- `patternTypeLabels()`   -> SPACES    (空間 7 種)
- `patternItemLabels()`   -> FURNITURE / APPLIANCE (傢俱 59、家電 35)
- `itemKeyMaps()`         -> ALIASES   (中文別名 -> key,102 條)

為什麼要有這一層:點交清單那端只認得這些 key。VLM 若回「電冰箱」「單人床架」
之類的自由文字,jgb2 對不上,使用者還是得手動重打一次,整個功能就白做了。
所以 `normalize_item()` 認不出來的一律回 None,由呼叫端丟棄——
**寧可漏報,不可誤報**:多填一個品項會讓點交清單憑空多出東西,
比少填一個更難被發現。

改這份表之前先確認 jgb2 那邊也改了,兩邊不同步會靜默短漏品項。
"""

from __future__ import annotations

import unicodedata
from typing import Dict, Optional

# 空間(pattern type)——jgb2 Estate::patternTypeLabels()
SPACES: Dict[str, str] = {
    "room": "房間",
    "living_room": "客廳/餐廳",
    "office": "辦公空間",
    "kitchen": "廚房",
    "bathroom": "衛浴",
    "balcony": "陽台",
    "household_item": "生活用品",
}

# 傢俱——jgb2 Estate::patternItemLabels()['furniture']
FURNITURE: Dict[str, str] = {
    "single_bed": "單人床",
    "double_bed": "雙人床",
    "bedside_table": "床頭櫃",
    "closet": "衣櫃",
    "table": "桌子",
    "chair": "椅子",
    "cabinet": "櫃子",
    "sofa": "沙發",
    "shoe_cabinet": "鞋櫃",
    "kitchen_fitment": "系統櫥櫃",
    "kitchen_table": "流理臺",
    "bathtub": "浴缸",
    "seperate_bathroom_toilet": "乾濕分離",
    "sitting_toilet": "坐式馬桶",
    "squatty_potty": "蹲式馬桶",
    "washstand": "洗手台",
    "clothes_rack": "曬衣架",
    "curtain": "窗簾組",
    "mat": "切菜墊",
    "fork": "叉子",
    "plate": "碟子",
    "dish_tray": "碟盤架",
    "frying_pan": "平底鍋",
    "cooking_knife": "廚房刀",
    "mug": "馬克杯",
    "bowl": "碗",
    "waste_bin": "垃圾桶",
    "pot_with_lid": "附蓋鍋子",
    "spoon": "湯匙",
    "teaspoon": "茶匙",
    "soap_container": "洗碗精容器",
    "roller_blind_curtain": "捲簾",
    "duvet": "羽絨被",
    "pillow": "枕頭",
    "cushion_insert_and_cover": "靠枕",
    "ironing_board": "燙衣板",
    "grille_door_key": "鐵門鑰匙",
    "letter_box_key": "信箱鑰匙",
    "main_door_key": "房門鑰匙",
    "key": "鑰匙",
    "tv_bracket": "電視支架",
    "amenities_tray": "盥洗用品托盤",
    "bathroom_amenities_tray": "浴室用品托盤",
    "toilet_brush": "馬桶刷",
    "parking_access_card": "停車場感應卡",
    "lift_access_card": "電梯感應卡",
    "universal_extension_plug": "通用延長插座",
    "shower_gel_container": "沐浴乳容器",
    "shampoo_container": "洗髮精容器",
    "towel_hook": "毛巾掛鉤",
    "cookware_3pcs": "鍋具三件組",
    "cooking_utensils_set": "烹飪用具組",
    "shower_gel_and_shampoo_container": "沐浴乳與洗髮精容器",
    "hanger": "衣架",
    "desk": "辦公桌",
    "desk_chairs": "辦公椅",
    "chest_of_drawers": "抽屜櫃",
    "locker": "置物櫃",
    "whiteboard": "白板",
}

# 家電——jgb2 Estate::patternItemLabels()['appliance']
APPLIANCE: Dict[str, str] = {
    "TV": "電視",
    "air_conditioner": "冷氣",
    "internet": "網路",
    "cableTV": "第四台",
    "range_hood": "排油煙機",
    "gas_cooktop": "瓦斯爐",
    "induction_cooktop": "電磁爐",
    "refrigerator": "冰箱",
    "microwave": "微波爐",
    "oven": "烤箱",
    "water_filter": "淨水器",
    "dish_dryer": "洗烘碗機",
    "exhaust_fan": "抽風機",
    "warm_air_dryer": "暖風乾燥機",
    "washing_machine": "洗衣機",
    "dryer_machine": "烘衣機",
    "gas_operated_hot_water_heater": "瓦斯熱水器",
    "electricity_operated_hot_water_heater": "電熱水器",
    "hand_shower": "蓮蓬頭沐浴組",
    "mini_storage_water_heater": "中繼式熱水器",
    "storage_water_heater": "儲熱式熱水器",
    "instant_water_heater": "即熱式熱水器",
    "solar_water_heater": "太陽能熱水器",
    "heater": "暖氣機",
    "intercom": "對講機",
    "remote_control": "遙控器",
    "condensing_dryer": "冷凝式乾衣機",
    "telephone": "室內電話",
    "lamp": "檯燈",
    "projector": "投影機",
    "monitor": "螢幕",
    "projection_screen": "投影幕",
    "electric_kettle": "電熱水壺",
    "iron": "熨斗",
    "hair_dryer": "吹風機",
}

# 傢俱 + 家電的合併表。兩邊 key 不重疊(已驗證),合併安全。
ITEMS: Dict[str, str] = {**FURNITURE, **APPLIANCE}

# 中文別名 -> key。jgb2 Estate::itemKeyMaps()。
# 一個 key 可以有多個別名(餐桌/茶几/梳妝台/書桌 全部 -> table),
# 這是刻意的:jgb2 的點交清單只有 table 這一格。
ALIASES: Dict[str, str] = {
    "單人床": "single_bed",
    "雙人床": "double_bed",
    "衣櫃": "closet",
    "桌子": "table",
    "餐桌": "table",
    "茶几": "table",
    "梳妝台": "table",
    "書桌": "table",
    "椅子": "chair",
    "餐桌椅": "chair",
    "書桌椅": "chair",
    "櫃子": "cabinet",
    "書櫃": "cabinet",
    "床組(頭)": "cabinet",
    "沙發": "sofa",
    "鞋櫃": "shoe_cabinet",
    "系統櫥櫃": "kitchen_fitment",
    "電視櫃": "kitchen_fitment",
    "流理臺": "kitchen_table",
    "浴缸": "bathtub",
    "乾濕分離": "seperate_bathroom_toilet",
    "坐式馬桶": "sitting_toilet",
    "蹲式馬桶": "squatty_potty",
    "洗手台": "washstand",
    "曬衣架": "clothes_rack",
    "辦公桌": "desk",
    "辦公椅": "desk_chairs",
    "抽屜櫃": "chest_of_drawers",
    "置物櫃": "locker",
    "白板": "whiteboard",
    "電視": "TV",
    "冷氣": "air_conditioner",
    "網路": "internet",
    "第四台": "cableTV",
    "排油煙機": "range_hood",
    "瓦斯爐": "gas_cooktop",
    "電磁爐": "induction_cooktop",
    "冰箱": "refrigerator",
    "微波爐": "microwave",
    "烤箱": "oven",
    "淨水器": "water_filter",
    "洗烘碗機": "dish_dryer",
    "洗碗機": "dish_dryer",
    "抽風機": "exhaust_fan",
    "暖風乾燥機": "warm_air_dryer",
    "洗衣機": "washing_machine",
    "烘衣機": "dryer_machine",
    "熱水器": "gas_operated_hot_water_heater",
    "瓦斯熱水器": "gas_operated_hot_water_heater",
    "電熱水器": "electricity_operated_hot_water_heater",
    "中繼式熱水器": "mini_storage_water_heater",
    "儲熱式熱水器": "storage_water_heater",
    "即熱式熱水器": "instant_water_heater",
    "太陽能熱水器": "solar_water_heater",
    "室內電話": "telephone",
    "檯燈": "lamp",
    "投影機": "projector",
    "螢幕": "monitor",
    "投影幕": "projection_screen",
    "蓮蓬頭沐浴組": "hand_shower",
    "床頭櫃": "bedside_table",
    "暖氣機": "heater",
    "切菜墊": "mat",
    "叉子": "fork",
    "碟子": "plate",
    "碟盤架": "dish_tray",
    "平底鍋": "frying_pan",
    "廚房刀": "cooking_knife",
    "馬克杯": "mug",
    "碗": "bowl",
    "垃圾桶": "waste_bin",
    "附蓋鍋子": "pot_with_lid",
    "湯匙": "spoon",
    "茶匙": "teaspoon",
    "洗碗精容器": "soap_container",
    "捲簾": "roller_blind_curtain",
    "電熱水壺": "electric_kettle",
    "冷凝式乾衣機": "condensing_dryer",
    "羽絨被": "duvet",
    "枕頭": "pillow",
    "靠枕": "cushion_insert_and_cover",
    "熨斗": "iron",
    "燙衣板": "ironing_board",
    "鐵門鑰匙": "grille_door_key",
    "信箱鑰匙": "letter_box_key",
    "房門鑰匙": "main_door_key",
    "鑰匙": "key",
    "電視支架": "tv_bracket",
    "盥洗用品托盤": "amenities_tray",
    "浴室用品托盤": "bathroom_amenities_tray",
    "馬桶刷": "toilet_brush",
    "停車場感應卡": "parking_access_card",
    "電梯感應卡": "lift_access_card",
    "通用延長插座": "universal_extension_plug",
    "沐浴乳容器": "shower_gel_container",
    "洗髮精容器": "shampoo_container",
    "毛巾掛鉤": "towel_hook",
    "鍋具三件組": "cookware_3pcs",
    "烹飪用具組": "cooking_utensils_set",
    "沐浴乳與洗髮精容器": "shower_gel_and_shampoo_container",
    "吹風機": "hair_dryer",
    "衣架": "hanger",
}

# 反查用的小寫索引。'TV'、'cableTV' 是混合大小寫的 key,
# 直接用 dict 查會漏掉模型回傳的 'tv',所以另建一份。
_ITEM_KEYS_LOWER: Dict[str, str] = {k.lower(): k for k in ITEMS}
_SPACE_KEYS_LOWER: Dict[str, str] = {k.lower(): k for k in SPACES}
_ITEM_LABELS: Dict[str, str] = {label: key for key, label in ITEMS.items()}
_SPACE_LABELS: Dict[str, str] = {label: key for key, label in SPACES.items()}


def _clean(value: object) -> str:
    """正規化比對用字串:NFKC + 去空白。

    NFKC 是必要的——全形英數與相容字元(例如 'ＴＶ')不做這步就整條比不到。
    中文詞內部也可能被塞空白('冷 氣'),一併去掉。
    """
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).strip()
    return "".join(text.split())


def normalize_item(value: object) -> Optional[str]:
    """把任意品項字串收斂成 jgb2 的品項 key;認不出來回 None。

    比對順序:key(不分大小寫) -> 官方中文 label -> 中文別名。
    """
    text = _clean(value)
    if not text:
        return None
    key = _ITEM_KEYS_LOWER.get(text.lower())
    if key:
        return key
    if text in _ITEM_LABELS:
        return _ITEM_LABELS[text]
    return ALIASES.get(text)


def normalize_space(value: object) -> Optional[str]:
    """把任意空間字串收斂成 jgb2 的空間 key;認不出來回 None。"""
    text = _clean(value)
    if not text:
        return None
    key = _SPACE_KEYS_LOWER.get(text.lower())
    if key:
        return key
    return _SPACE_LABELS.get(text)


def category_of(key: str) -> Optional[str]:
    """品項 key 屬於 'furniture' 還是 'appliance';不是合法 key 回 None。"""
    if key in FURNITURE:
        return "furniture"
    if key in APPLIANCE:
        return "appliance"
    return None


def prompt_vocabulary() -> str:
    """給 VLM 提示詞用的詞彙清單(繁中 label,逗號分隔)。

    只餵 label 不餵 key:模型看中文的命中率明顯高於看 snake_case,
    回來之後再由 normalize_item() 轉回 key。
    """
    return (
        "空間(擇一):" + "、".join(SPACES.values()) + "\n"
        + "傢俱:" + "、".join(FURNITURE.values()) + "\n"
        + "家電:" + "、".join(APPLIANCE.values())
    )
