"""闲鱼商品列表/详情解析单元测试。

对 mtop 返回结构的字段提取与缺省值做回归。"""

from __future__ import annotations

import json
import unittest

from dingda_sidecar.crawlers.goofish.item import parse_item_detail, parse_list_page


class XianyuItemParseTests(unittest.TestCase):
    def test_parse_card_list(self) -> None:
        data = {
            "cardList": [
                {
                    "cardData": {
                        "main": {"title": "二手手机", "soldPrice": "128.5"},
                        "detailParams": {"itemId": "1234567890"},
                    }
                }
            ]
        }
        items = parse_list_page(data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["item_id"], "1234567890")
        self.assertEqual(items[0]["title"], "二手手机")
        self.assertAlmostEqual(items[0]["price"], 128.5)

    def test_parse_item_detail(self) -> None:
        data = {
            "itemDO": {
                "title": "二手手机",
                "soldPrice": "199.5",
                "originalPrice": "299",
                "desc": "备用描述",
                "wantCnt": 8,
                "browseCnt": 120,
                "imageInfos": [{"url": "https://img.example/1.jpg"}],
            }
        }
        detail = parse_item_detail(data, "123")
        self.assertEqual(detail["item_id"], "123")
        self.assertEqual(detail["title"], "二手手机")
        self.assertAlmostEqual(detail["price"], 199.5)
        self.assertEqual(detail["want_count"], 8)

    def test_parse_item_detail_share_json(self) -> None:
        share = {
            "contentParams": {
                "mainParams": {
                    "content": "真正文案\n第二行",
                    "images": [{"image": "https://img.example/hd.jpg"}],
                }
            }
        }
        data = {
            "itemDO": {
                "title": "",
                "soldPrice": 50,
                "shareData": {"shareInfoJsonString": json.dumps(share, ensure_ascii=False)},
            }
        }
        detail = parse_item_detail(data, "999")
        self.assertEqual(detail["desc"], "真正文案\n第二行")
        self.assertEqual(detail["images"], ["https://img.example/hd.jpg"])


if __name__ == "__main__":
    unittest.main()
