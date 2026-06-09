from pydantic import BaseModel, Field
from typing import List, Optional

class ChunkMetadata(BaseModel):
    id: str = Field(..., description="Identifiant unique du chunk")
    source: str = Field(..., description="Fichier source d'origine")
    equipes: List[str] = Field(default_factory=list, description="Équipes de football mentionnées dans le chunk")
    tags_tactiques: List[str] = Field(default_factory=list, description="Concepts tactiques associés (ex: pressing, low-block)")
    type_chunk: str = Field("general", description="Type de contenu (ex: tactique, exercice, match, historique)")

class ProcessedChunk(BaseModel):
    text: str = Field(..., description="Contenu textuel nettoyé du chunk")
    metadata: ChunkMetadata = Field(..., description="Métadonnées validées associées")
