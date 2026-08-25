"""embedding dim 1024 for openrouter free embedding model

Switches document_chunks.embedding from vector(1536) (OpenAI
text-embedding-3-small) to vector(1024) to match the free
liquid/lfm-2.5-embedding-350m:free model on OpenRouter - see
specs/DEVOPS.md §3 (EMBEDDING_* settings) and specs/TECHNOLOGIES.md
(EmbeddingProvider is a swappable port). Any existing embeddings are of the
old dimensionality and can't be cast in place, so they're cleared; affected
documents need to be re-uploaded to be searchable again.

Revision ID: 3b33e8bac7bb
Revises: cd500eaf328a
Create Date: 2026-08-24 20:39:24.831538

"""

from collections.abc import Sequence

from alembic import op

revision: str = "3b33e8bac7bb"
down_revision: str | Sequence[str] | None = "cd500eaf328a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_DIM = 1536
_NEW_DIM = 1024


def upgrade() -> None:
    op.drop_index("idx_chunks_embedding_hnsw", table_name="document_chunks")
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({_NEW_DIM})")
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_index("idx_chunks_embedding_hnsw", table_name="document_chunks")
    op.execute("UPDATE document_chunks SET embedding = NULL")
    op.execute(f"ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector({_OLD_DIM})")
    op.execute(
        "CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
