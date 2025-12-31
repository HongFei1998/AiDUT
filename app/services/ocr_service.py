import time
import traceback
import cv2
from paddleocr import PaddleOCR
import logging


class ocr_service():
    def __init__(self, lang='ch'):
        log = logging.getLogger('ppocr')
        log.setLevel('ERROR')

        # 百度飞浆OCR  ocr_version="PP-OCR" 可选模型，当前用的是v3准确率最高
        self.ocr_v3 = PaddleOCR(use_gpu=False, lang=lang, ocr_version="PP-OCRv3", use_angle_cls=False,
                                enable_mkldnn=True)

    def get_all_text_with_positions(self, image_path):
        """
        识别图片中的所有文字并返回文字及其坐标信息
        用于将OCR结果传递给AI，而不是直接传递截图
        :param image_path: 图片路径
        :return: 包含所有文字及坐标的列表，格式为:
                 [
                     {
                         "text": "识别的文字",
                         "center": (x, y),           # 文字区域中心点坐标
                         "bounds": {                  # 文字区域边界框
                             "left": x1,
                             "top": y1,
                             "right": x2,
                             "bottom": y2
                         },
                         "confidence": 0.95           # 识别置信度
                     },
                     ...
                 ]
        """
        ocr = self.ocr_v3
        result_list = []
        
        try:
            # cv2读取图片
            img = cv2.imread(image_path, 0)
            if img is None:
                return {"error": f"无法读取图片: {image_path}", "elements": []}
            
            result = ocr.ocr(img, cls=False)[0]
            
            if result is None:
                return {"error": None, "elements": []}
            
            for line in result:
                # line[0] 是四个角点坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                # line[1] 是 (识别文字, 置信度)
                points = line[0]
                text = line[1][0]
                confidence = line[1][1]
                
                # 计算边界框
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                left = min(x_coords)
                right = max(x_coords)
                top = min(y_coords)
                bottom = max(y_coords)
                
                # 计算中心点
                center_x = (left + right) / 2
                center_y = (top + bottom) / 2
                
                result_list.append({
                    "text": text,
                    "center": (int(center_x), int(center_y)),
                    "bounds": {
                        "left": int(left),
                        "top": int(top),
                        "right": int(right),
                        "bottom": int(bottom)
                    },
                    "confidence": round(confidence, 4)
                })
            
            return {"error": None, "elements": result_list}
            
        except Exception as e:
            print(traceback.format_exc())
            return {"error": str(e), "elements": []}

    def get_screen_text_for_ai(self, image_path):
        """
        获取屏幕文字信息的格式化输出，专门用于传递给AI
        :param image_path: 截图路径
        :return: 格式化的字符串，描述屏幕上的所有可见文字及位置
        """
        result = self.get_all_text_with_positions(image_path)
        
        if result["error"]:
            return f"OCR识别出错: {result['error']}"
        
        if not result["elements"]:
            return "屏幕上未识别到任何文字"
        
        # 按从上到下、从左到右的顺序排序
        elements = sorted(result["elements"], key=lambda x: (x["bounds"]["top"], x["bounds"]["left"]))
        
        lines = ["当前屏幕识别到的文字元素:"]
        lines.append("-" * 50)
        
        for i, elem in enumerate(elements, 1):
            lines.append(f"{i}. \"{elem['text']}\"")
            lines.append(f"   坐标: 中心点({elem['center'][0]}, {elem['center'][1]})")
            lines.append(f"   区域: 左上({elem['bounds']['left']}, {elem['bounds']['top']}) 右下({elem['bounds']['right']}, {elem['bounds']['bottom']})")
            lines.append(f"   置信度: {elem['confidence']}")
        
        lines.append("-" * 50)
        lines.append(f"共识别到 {len(elements)} 个文字元素")
        
        return "\n".join(lines)

    def get_position_from_ocr_by_paddle(self, image_path, target_str, contains_flag=True):
        """
        从目标图片中查找目标文字的位置
        :param image_path: 待查找图片
        :param target_str: 待查找文字
        :param contains_flag: 默认是包含查找，因为ocr有时候会识别不太准确
        :return:
        """
        ocr = self.ocr_v3
        return_list = []
        start_time = time.time()

        # cv2
        img = cv2.imread(image_path, 0)

        result = ocr.ocr(img, cls=False)[0]
        if contains_flag:
            for line in result:
                if target_str in line[-1][0]:
                    return_list.append(((line[0][0][0] + line[0][1][0]) / 2, (line[0][0][1] + line[0][2][1]) / 2))
        else:
            for line in result:
                if target_str == line[-1][0]:
                    return_list.append(((line[0][0][0] + line[0][1][0]) / 2, (line[0][0][1] + line[0][2][1]) / 2))
        return return_list

    def get_str(self, image_path, target_length=None):
        """
        根据图片解析图片中的文字，通常用作解验证码，仅在图片中找到一处文字时返回
        :param image_path: 图片地址
        :param target_length: 目标文字长度
        :return:
        """
        ocr = self.ocr_v3
        # cv2
        img = cv2.imread(image_path, 0)
        try:
            result = ocr.ocr(img, cls=False)[0]
            if len(result) == 1:
                if target_length:
                    return result[0][-1][0][-target_length:]
                else:
                    return result[0][-1][0]
            else:
                return None
        except Exception as e:
            print(traceback.format_exc())
            return None


if __name__ == "__main__":
    OCR = ocr_service()
    start_time = time.time()
    
    # 测试获取所有文字及坐标
    print("=== 测试 get_all_text_with_positions ===")
    result = OCR.get_all_text_with_positions(r'./captcha.png')
    print(result)
    
    print("\n=== 测试 get_screen_text_for_ai ===")
    ai_text = OCR.get_screen_text_for_ai(r'./captcha.png')
    print(ai_text)
    
    print("\n=== 测试 get_position_from_ocr_by_paddle ===")
    print(OCR.get_position_from_ocr_by_paddle(r'./captcha.png', "项目", True))
    
    print('\n总用时：', time.time() - start_time)
