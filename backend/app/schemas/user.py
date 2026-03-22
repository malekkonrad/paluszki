

class User(BaseModel):
    id: int = Field(ge=1, examples=[1])
    email: EmailStr = Field(examples=["john.smith@gmail.com"])
    name: str = Field(examples=["John"])
    surname: str = Field(examples=["Smith"])
