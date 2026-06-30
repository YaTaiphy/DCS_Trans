import requests


IP_ADDRESS = "121.41.75.139"
PORT = 10386

def looking_translated(mizNameBase16):
    # 远程请求查找，如果存在并且查找到，返回True和相关内容，否则返回False和相关错误
    # @app.route('/health', methods=['GET'])
    # def health_check():
    #     return jsonify({'status': 'Flask server is running'})
    # 检查远程服务器是否可用
    try:
        response = requests.get(f"http://{IP_ADDRESS}:{PORT}/health", timeout=5)
        if response.status_code == 200:
            print("远程服务器可用，尝试查找翻译结果...")
            # 发送查找请求
            response = requests.post(f"http://{IP_ADDRESS}:{PORT}/looking_translated", json={"mizNameBase16": mizNameBase16}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return True, data.get("content")
                else:
                    return False, data.get("message", "未知错误")
    except requests.RequestException as e:
        print(f"远程服务器请求失败: {e}")
    return False, "未实现远程查找功能"

def save_translated(mizNameBase16, translatedContentJson):
    # 远程请求保存翻译结果，如果保存成功，返回True，否则返回False和相关错误
    try:
        response = requests.post(f"http://{IP_ADDRESS}:{PORT}/save_translated", json={"mizNameBase16": mizNameBase16, "translatedContentJson": translatedContentJson}, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return True, "保存成功"
            else:
                return False, data.get("message", "未知错误")
    except requests.RequestException as e:
        print(f"远程服务器请求失败: {e}")
    
    return False, "未实现远程保存功能"

if __name__ == "__main__":
    # 测试looking_translated函数
    test_hash = "test_hash_value"
    is_found, content = looking_translated(test_hash)
    if is_found:
        print(f"远程查找成功，内容为: {content}")
    else:
        print(f"远程查找失败，错误信息: {content}")