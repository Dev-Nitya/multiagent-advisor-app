from config.database import get_db
from models.prompt import Prompt

class PromptRegistry:
    def __init__(self):
        pass

    def _generate_hash(self, prompt_text: str, model_settings: dict, output_schema: dict) -> str:
        import hashlib
        hash_input = prompt_text + str(model_settings) + str(output_schema)
        return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

    def create_versioned_prompt(self, name: str, prompt_text: str, model_settings: dict, output_schema: dict, author: str, changelog: str) -> Prompt:
        """
        Create a new versioned prompt. If a prompt with the same name exists,
        increment its version number.
        """
        db = next(get_db())
        existing_prompts = db.query(Prompt).filter(Prompt.name == name).all()
        if existing_prompts:
            latest_version = max(p.version for p in existing_prompts)
            new_version = latest_version + 1
        else:
            new_version = 1

        prompt_hash = self._generate_hash(prompt_text, model_settings, output_schema)

        new_prompt = Prompt(
            name=name,
            version=new_version,
            prompt_text=prompt_text,
            model_settings=model_settings,
            output_schema=output_schema,
            hash=prompt_hash,
            author=author,
            changelog=changelog
        )
        db.add(new_prompt)
        db.commit()
        db.refresh(new_prompt)
        return new_prompt
    
    def get_prompt_by_id(self, prompt_id: str) -> Prompt:
        db = next(get_db())
        return db.query(Prompt).filter(Prompt.prompt_id == prompt_id).first()
    
    def get_latest_prompt_by_name(self, name: str) -> Prompt:
        db = next(get_db())
        return db.query(Prompt).filter(Prompt.name == name).order_by(Prompt.version.desc()).first()
    
    def get_latest_prompt_id(self) -> str | None:
        db = next(get_db())
        latest_prompt = db.query(Prompt).order_by(Prompt.created_at.desc()).first()
        return latest_prompt.prompt_id if latest_prompt else None
    
    def get_all_prompts(self) -> list[Prompt]:
        db = next(get_db())
        return db.query(Prompt).all()
    
prompt_registry = PromptRegistry()