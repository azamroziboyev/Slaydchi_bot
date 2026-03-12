import random
#this saves the keys for the mexanizm
keys = [
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
    "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",
    "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"
]

#this saves the models for the mexanizm
models = ["openai/gpt-oss-20b:free", 
          "google/gemma-3-27b-it:free", 
          "google/gemma-3-12b-it:free", 
          "tngtech/deepseek-r1t2-chimera:free", 
           "deepseek/deepseek-r1-0528:free",
           "tngtech/deepseek-r1t-chimera:free",
           "stepfun/step-3.5-flash:free",
           "arcee-ai/trinity-large-preview:free",
           "liquid/lfm-2.5-1.2b-thinking:free",
           "liquid/lfm-2.5-1.2b-instruct:free",
           "nvidia/nemotron-3-nano-30b-a3b:free",
           "qwen/qwen3-next-80b-a3b-instruct:free",
           "qwen/qwen3-next-80b-a3b-instruct",
           "mistralai/mistral-small-3.1-24b-instruct:free"
        ]

########################################
#### BU yerda kalitlar bilan ishlaydigan funksiyalar bo'ladi ####
####################################################

class APIKeyManager:
    def __init__(self, keys):
        self.keys = keys  # Asl ro'yxat
        self.current_index = 0

    def get_next_key(self):
        if not self.keys:
            return None
        # Navbatdagi kalitni tanlash
        key = self.keys[self.current_index % len(self.keys)]
        self.current_index += 1
        return key

    def remove_broken_key(self, key):
        if key in self.keys:
            self.keys.remove(key)
            print(f"❌ Kalit o'chirildi: {key}")
            
            # Siz aytgan shart: 5 tadan kam qolsa xabar berish
            if len(self.keys) < 5:
                self.alert_admin_key(len(self.keys))

    def alert_admin_key(self, count):
        # Bu yerda admin (o'zingizga) xabar yuborish funksiyasi bo'ladi
        print(f"⚠️ DIQQAT! Atigi {count} ta kalit qoldi!")
        return "attention"

#####################################

###### Bu yerda modellar bilan ishlaydigan funksiyalar bo'ladi ######

####################################

class ModelManager:
    def __init__(self, models):
        self.models = models  # Modellar ro'yxati (masalan, ["gpt-4", "claude-3"])
        self.current_index = 0

    def get_next_model(self):
        if not self.models:
            return None
        # Navbatdagi modelni tanlash
        model = self.models[self.current_index % len(self.models)]
        self.current_index += 1
        return model

    def remove_broken_model(self, model):
        """Agar model xato bersa, uni o'chirib tashlash"""
        if model in self.models:
            self.models.remove(model)
            print(f"❌ Model o'chirildi: {model}")
            
            # Siz aytgan shart: 3 tadan kam qolsa xabar berish
            if len(self.models) < 3:
                self.alert_admin_model(len(self.models))

    def alert_admin_model(self, count):
        # print(f"⚠️ DIQQAT! Atigi {count} ta model qoldi!")
        return "attention"

# yangi model va keylarni qo'shish
def insert_key(new_key):
    keys.append(new_key)


def insert_model(new_model):
    models.append(new_model)
    return len(models)
    
def show_models():
    return models


