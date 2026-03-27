"""
OCR 辨識測試與驗證 API

提供 OCR 辨識效果的測試、對比與驗證功能
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from PIL import Image
import fitz
from io import BytesIO
import os
from typing import Optional, List, Literal

from app.lib.ocr_enhanced.preprocessor import TranscriptPreprocessor
from app.lib.ocr_enhanced.config import PreprocessConfig
from app.lib.ocr_enhanced.engine_manager import EngineManager
from app.lib.ocr_enhanced.postprocessor import TranscriptPostprocessor
from app.lib.multi_type_ocr.processor_factory import ProcessorFactory

router = APIRouter()


@router.post(
    "/test",
    responses={
        200: {
            "description": "OCR 辨識成功",
            "content": {
                "application/json": {
                    "examples": {
                        "transcript": {
                            "summary": "謄本辨識範例",
                            "value": {
                                "file_name": "transcript.pdf",
                                "total_pages": 1,
                                "document_type": "transcript",
                                "pages": [{
                                    "page_number": 1,
                                    "original_image": "data:image/png;base64,...",
                                    "ocr_raw": {
                                        "text": "土地登記謄本...",
                                        "confidence": 0.8543
                                    },
                                    "rule_postprocessed": {
                                        "text": "土地登記謄本...",
                                        "stats": {"typo_fixes": 12}
                                    },
                                    "llm_postprocessed": None,
                                    "structured_data": {},
                                    "processing_steps": {
                                        "1_ocr_engine": "Tesseract",
                                        "2_rule_processing": "✓ 完成",
                                        "3_llm_processing": "⊗ 未使用"
                                    }
                                }]
                            }
                        },
                        "contract": {
                            "summary": "合約辨識範例",
                            "value": {
                                "file_name": "contract.pdf",
                                "total_pages": 1,
                                "document_type": "contract",
                                "pages": [{
                                    "page_number": 1,
                                    "original_image": "data:image/png;base64,...",
                                    "ocr_raw": {
                                        "text": "買賣契約書...",
                                        "confidence": 0.8234
                                    },
                                    "rule_postprocessed": {
                                        "text": "買賣契約書...",
                                        "stats": {"typo_fixes": 8}
                                    },
                                    "llm_postprocessed": None,
                                    "structured_data": {
                                        "contract_metadata": {
                                            "contract_number": "ABC-2024-001",
                                            "signing_date": "2024-01-15",
                                            "effective_date": "2024-02-01"
                                        },
                                        "parties": {
                                            "party_a": "甲方公司",
                                            "party_b": "乙方公司",
                                            "party_a_address": None,
                                            "party_b_address": None
                                        },
                                        "financial_terms": {
                                            "contract_amount": "1000000",
                                            "currency": "TWD",
                                            "payment_method": None,
                                            "payment_deadline": None
                                        },
                                        "extraction_confidence": 0.72
                                    },
                                    "processing_steps": {
                                        "1_ocr_engine": "Tesseract",
                                        "2_rule_processing": "✓ 完成",
                                        "3_llm_processing": "⊗ 未使用"
                                    }
                                }]
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "參數錯誤",
            "content": {
                "application/json": {
                    "examples": {
                        "unsupported_type": {
                            "summary": "不支援的文件類型",
                            "value": {
                                "detail": "不支援的文件類型: invoice。支援的類型: transcript, contract"
                            }
                        },
                        "invalid_page": {
                            "summary": "無效的頁碼",
                            "value": {
                                "detail": "無效的頁碼。PDF 共有 3 頁，請選擇 1-3 之間的頁碼"
                            }
                        }
                    }
                }
            }
        },
        500: {
            "description": "處理失敗",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "OCR 測試失敗: 處理過程發生錯誤"
                    }
                }
            }
        }
    }
)
async def test_ocr(
    file: UploadFile = File(..., description="PDF 或圖片檔案（支援 .pdf, .jpg, .jpeg, .png）"),
    enable_llm: bool = Query(
        default=True,
        description="是否啟用 LLM 視覺修正（true: 使用 GPT-4o 看圖修正，false: 只使用規則後處理）"
    ),
    ground_truth: Optional[str] = Query(
        default=None,
        description="標準答案文字，用於計算準確率"
    ),
    page_number: Optional[int] = Query(
        default=None,
        description="指定處理的頁碼（null 或不提供則處理所有頁面）",
        ge=1
    ),
    document_type: Literal["transcript", "contract"] = Query(
        default="transcript",
        description="文件類型（transcript: 謄本文件, contract: 合約文件）"
    )
):
    """
    ## OCR 辨識測試

    上傳 PDF 或圖片進行 OCR 辨識測試，並返回對比結果。

    ### 功能特色
    - ✅ **多頁處理**: 自動處理 PDF 所有頁面
    - ✅ **視覺修正**: 使用 LLM 看圖修正 OCR 錯誤
    - ✅ **準確率對比**: 對比原始 OCR、規則後處理、LLM 修正的效果
    - ✅ **成本追蹤**: 顯示 LLM 處理成本

    ### 參數說明
    - **file** (必填): PDF 或圖片檔案
      - 支援格式: `.pdf`, `.jpg`, `.jpeg`, `.png`
      - 大小限制: 20MB
      - 多頁 PDF 會自動處理所有頁面

    - **document_type** (選填, 預設="transcript"): 文件類型
      - `transcript`: 謄本文件（預設）
      - `contract`: 合約文件
      - 不同文件類型會使用對應的處理器與欄位提取

    - **enable_llm** (選填, 預設=true): 是否啟用 LLM 視覺修正
      - `true`: 使用 GPT-4o 看圖修正（成本約 $0.02-0.03/頁）
      - `false`: 只使用規則後處理（免費）

    - **ground_truth** (選填): 標準答案文字
      - 用於計算準確率
      - 提供後會在結果中顯示各處理方式的準確率

    - **page_number** (選填): 指定處理的頁碼
      - `null` 或不提供: 處理所有頁面（預設）
      - 數字 (1-N): 只處理指定頁

    ### 返回結果
    ```json
    {
      "file_name": "檔案名稱.pdf",
      "total_pages": 3,
      "pages": [
        {
          "page_number": 1,
          "original_image": "data:image/png;base64,...",
          "ocr_raw": {
            "text": "原始 OCR 文字",
            "confidence": 0.7943
          },
          "rule_postprocessed": {
            "text": "規則後處理文字",
            "stats": {
              "typo_fixes": 25,
              "format_corrections": 4
            }
          },
          "llm_postprocessed": {
            "text": "LLM 修正後文字",
            "stats": {
              "llm_used": true,
              "llm_cost": 0.025
            },
            "used": true
          },
          "accuracy": {
            "raw": 65.75,
            "rule": 67.01,
            "llm": 77.84
          },
          "processing_steps": {
            "1_ocr_engine": "Tesseract",
            "2_rule_processing": "✓ 完成",
            "3_llm_processing": "✓ 完成（視覺修正）"
          }
        }
      ]
    }
    ```

    ### 使用範例

    **基本使用**（只做 OCR，不使用 LLM）:
    ```bash
    curl -X POST "http://localhost:8003/api/v1/ocr/test" \\
      -F "file=@document.pdf" \\
      -F "enable_llm=false"
    ```

    **完整測試**（含 LLM 視覺修正和準確率計算）:
    ```bash
    curl -X POST "http://localhost:8003/api/v1/ocr/test" \\
      -F "file=@document.pdf" \\
      -F "enable_llm=true" \\
      -F "ground_truth=正確的文字內容..."
    ```

    ### 注意事項
    - LLM 修正需要設定 `OPENAI_API_KEY` 環境變數
    - 大文件處理時間較長，建議分批處理
    - 智能策略: OCR 信心度 < 85% 才使用 LLM（節省成本）
    """
    try:
        # 驗證 document_type 參數
        supported_types = ProcessorFactory.supported_types()
        if document_type not in supported_types:
            raise HTTPException(
                status_code=400,
                detail=f"不支援的文件類型: {document_type}。支援的類型: {', '.join(supported_types)}"
            )

        # 讀取檔案內容
        contents = await file.read()

        # 判斷檔案類型
        is_pdf = file.filename.lower().endswith('.pdf')

        if is_pdf:
            # 取得 PDF 總頁數
            doc = fitz.open(stream=contents, filetype="pdf")
            total_pages = len(doc)
            doc.close()

            # 決定要處理哪些頁面
            if page_number is not None:
                # 處理單頁
                pages_to_process = [page_number]
            else:
                # 處理所有頁
                pages_to_process = list(range(1, total_pages + 1))
        else:
            # 圖片只有一頁
            total_pages = 1
            pages_to_process = [1]

        # 處理每一頁
        results = []
        for page_num in pages_to_process:
            page_result = await _process_single_page(
                contents,
                file.filename,
                page_num,
                total_pages,
                enable_llm,
                ground_truth,
                is_pdf,
                document_type
            )
            results.append(page_result)

        # 返回結果
        return {
            "file_name": file.filename,
            "total_pages": total_pages,
            "document_type": document_type,
            "pages": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 測試失敗: {str(e)}")


async def _process_single_page(
    file_contents: bytes,
    filename: str,
    page_number: int,
    total_pages: int,
    enable_llm: bool,
    ground_truth: Optional[str],
    is_pdf: bool,
    document_type: str
) -> dict:
    """處理單一頁面的 OCR

    使用 ProcessorFactory 獲取對應的文件處理器，調用統一的 process() 方法。
    保持向後兼容性，支援 ground_truth 準確率計算。
    """
    import base64
    import difflib

    # 步驟 1: 提取單頁圖片內容
    if is_pdf:
        # PDF 需要提取指定頁面
        doc = fitz.open(stream=file_contents, filetype="pdf")
        page = doc[page_number - 1]  # 轉換為 0-based index
        mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        page_contents = img_data
        doc.close()
    else:
        # 圖片直接使用原始內容
        page_contents = file_contents

    # 步驟 2: 使用 ProcessorFactory 獲取處理器
    processor = ProcessorFactory.get_processor(document_type)

    # 步驟 3: 調用處理器的統一處理方法
    result = await processor.process(
        file_contents=page_contents,
        filename=filename,
        page_number=page_number,
        total_pages=total_pages,
        enable_llm=enable_llm
    )

    # 步驟 4: 如果提供了 ground_truth，計算準確率（向後兼容）
    if ground_truth:
        def calc_accuracy(gt: str, text: str) -> float:
            gt_clean = ''.join(gt.split())
            text_clean = ''.join(text.split())
            matcher = difflib.SequenceMatcher(None, gt_clean, text_clean)
            return matcher.ratio() * 100

        raw_text = result["ocr_raw"]["text"]
        rule_text = result["rule_postprocessed"]["text"]

        # 取前 1/3 的文字進行比對（與原邏輯一致）
        raw_portion = raw_text[:len(raw_text)//3]
        rule_portion = rule_text[:len(rule_text)//3]

        accuracy = {
            "raw": round(calc_accuracy(ground_truth, raw_portion), 2),
            "rule": round(calc_accuracy(ground_truth, rule_portion), 2)
        }

        # 如果有 LLM 修正結果，也計算 LLM 準確率
        if result.get("llm_postprocessed") and result["llm_postprocessed"].get("used"):
            llm_text = result["llm_postprocessed"]["text"]
            llm_portion = llm_text[:len(llm_text)//3]
            accuracy["llm"] = round(calc_accuracy(ground_truth, llm_portion), 2)
        else:
            accuracy["llm"] = None

        # 將準確率加入結果
        result["accuracy"] = accuracy

    return result


async def _extract_pdf_page(pdf_bytes: bytes, page_number: int = 1) -> tuple[Image.Image, int]:
    """從 PDF 提取指定頁為圖片

    Args:
        pdf_bytes: PDF 檔案的 bytes
        page_number: 頁碼（從 1 開始）

    Returns:
        (PIL Image, 總頁數)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    # 驗證頁碼
    if page_number < 1 or page_number > total_pages:
        doc.close()
        raise HTTPException(
            status_code=400,
            detail=f"無效的頁碼。PDF 共有 {total_pages} 頁，請選擇 1-{total_pages} 之間的頁碼"
        )

    page = doc[page_number - 1]  # 轉換為 0-based index
    mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
    pix = page.get_pixmap(matrix=mat)
    img_data = pix.tobytes("png")
    pil_image = Image.open(BytesIO(img_data))
    doc.close()
    return pil_image, total_pages
