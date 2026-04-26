import os
import glob
import json
import time
import base64
import requests
from loguru import logger
IMAGE_DIR = "/Users/halu/Library/Mobile Documents/com~apple~CloudDocs/Work/2026 work/02 AI Projects/01 平面诊断（基于集团标准）/资料/C2工具"

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set. Please set it before running this script.")
        print('Example: export GEMINI_API_KEY="您的真实Google_API_Key"')
        return

    # Endpoint configuration (Support for third-party proxies)
    base_url = os.environ.get("API_BASE_URL", "https://generativelanguage.googleapis.com").rstrip('/')
    url = f"{base_url}/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Get all png files and sort them numerically
    image_paths = glob.glob(os.path.join(IMAGE_DIR, "*.png"))
    
    def extract_number(path):
        basename = os.path.basename(path)
        num_str = basename.split('.')[0]
        try:
            return int(num_str)
        except ValueError:
            return 99999
            
    image_paths.sort(key=extract_number)
    
    logger.info(f"Found {len(image_paths)} images to process.")

    all_rules = []
    
    # Turn off test mode to process the remaining images
    test_mode = False
    
    # Support resuming from previous runs
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_rules.json")
    processed_images = set()
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                all_rules = json.load(f)
                for r in all_rules:
                    if "source_image" in r:
                        processed_images.add(r["source_image"])
            logger.info(f"Loaded {len(all_rules)} existing rules. Skipping {len(processed_images)} already processed images.")
        except Exception:
            pass
            
    images_to_process = [p for p in image_paths if os.path.basename(p) not in processed_images]
    
    if test_mode:
        logger.info("Running in TEST MODE: Only processing the first 5 images.")
        images_to_process = images_to_process[:5]

    for img_path in images_to_process:
        logger.info(f"Processing {os.path.basename(img_path)}...")
        
        try:
            with open(img_path, "rb") as image_file:
                b64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
            prompt = """
            你是一个资深的商业建筑审核专家和数据规范化专家。
            请仔细查看这张商业建筑（龙湖集团等）的设计标准截图。
            
            你的任务是：提取截图中的核心规范与标准，并按照以下的 JSON 结构返回。
            
            要求：
            1. 仔细阅读图片中的每一个字，特别是带数值、条件、业态说明的部分。
            2. 将每个独立的要求提炼成一条规则。如果图片里包含多条互不相关的规则，请将其拆分。
            3. 遇到表格时，请按行提取。
            4. 必须有 "category" (体系/模块，例如：动线、层高、卫生间等)。
            5. 必须有 "rule_desc" (规则详细描述)。
            6. 如果有判断尺寸或是否的指标，请尽量提取 "metric" (例如：走道宽度) 和 "value" (例如：>=2.0m)。
            
            返回格式必须为纯 JSON 数组，例如：
            [
              {
                "category": "商业动线",
                "target": "次要走道",
                "metric": "宽度",
                "value": ">= 2.0m",
                "rule_desc": "商业次要动线走道宽度不得小于2.0米"
              }
            ]
            
            如果图片中没有实质性的规范数据（如纯封面），请返回空数组 []。
            """
            
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": b64_image
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json"
                }
            }
            
            success = False
            attempt = 0
            while attempt < 100: # 接近无限重试，直到成功为止
                res = requests.post(url, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    response_json = res.json()
                    
                    # 尝试解析内容 (符合原生 Gemini REST API 格式)
                    try:
                        content_str = response_json["candidates"][0]["content"]["parts"][0]["text"]
                    except (KeyError, IndexError):
                        logger.error(f"Unexpected response structure: {response_json}")
                        break
                    
                    # 移除 markdown 代码块如 ```json ... ```
                    if content_str.startswith("```json"):
                        content_str = content_str[7:]
                    if content_str.startswith("```"):
                        content_str = content_str[3:]
                    if content_str.endswith("```"):
                        content_str = content_str[:-3]
                    
                    content_str = content_str.strip()
                    
                    try:
                        parsed_rules = json.loads(content_str)
                        for rule in parsed_rules:
                            rule["source_image"] = os.path.basename(img_path)
                        all_rules.extend(parsed_rules)
                        
                        # ✅ 即时保存：每个成功项立刻写入硬盘，不留遗憾
                        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_rules.json")
                        with open(output_path, "w", encoding="utf-8") as f:
                             json.dump(all_rules, f, ensure_ascii=False, indent=2)
                             
                        logger.success(f"Successfully extracted {len(parsed_rules)} rules from {os.path.basename(img_path)}. (Total memory rules: {len(all_rules)})")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse JSON for {os.path.basename(img_path)}. Raw text: {content_str}")
                    
                    success = True
                    break
                    
                elif res.status_code == 429: # Too Many Requests
                    if attempt == 0:
                        logger.warning(f"触发基础防护。初步冷却等待 60 秒...")
                        time.sleep(60)
                    else:
                        logger.warning(f"资源枯竭警报！正在执行全自动深度休眠：停止 30 分钟 (1800秒) 以等待额度重置...")
                        time.sleep(1800)
                        logger.info(f"休眠结束，自动发起对 {os.path.basename(img_path)} 的复苏重试...")
                    attempt += 1
                else: # 400 Bad Request / Other Error
                    logger.error(f"HTTP {res.status_code} Error on {os.path.basename(img_path)}: {res.text}")
                    # 不重试直接中断该图处理，避免死循环消耗额度
                    break
                    
            if not success:
                logger.error(f"Failed completely on {os.path.basename(img_path)} after exhaustive attempts.")
            
            # 严格限流保护 (每张图均摊 5 秒以上，结合前面的重试完美规避 15RPM)
            time.sleep(6)
            
        except Exception as e:
            logger.error(f"Error processing {os.path.basename(img_path)}: {e}")
            logger.warning("触发全局风控！强制进入深度冷却 60 秒以恢复配额...")
            time.sleep(60)
            
    logger.info("✅ Extraction completely finished.")

if __name__ == "__main__":
    main()
