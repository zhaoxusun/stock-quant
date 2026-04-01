import os
import requests

from common.logger import create_log

logger = create_log('ai_manager')


class AIManager:
    def __init__(self, model="gpt-4o-mini"):
        self.model = model
        self.github_token = os.environ.get('GITHUB_MODEL_TOKEN', '')

    def get_response(self, user_prompt):
        try:
            response = self.generate_analysis_github_ai(prompt=user_prompt)
            return response
        except Exception as e:
            return f"错误: {str(e)}"

    def generate_analysis_github_ai(self, prompt):
        url = "https://models.github.ai/inference/chat/completions"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # 检查请求是否成功

        result = response.json()
        return result['choices'][0]['message']['content']


if __name__ == '__main__':

    ai_manager = AIManager("grok-3")
    response = ai_manager.get_response("who are you?")
    # ai_manager = AIManager("DeepSeek-V3-0324")
    # response = ai_manager.get_response("who are you?")
    print(response)