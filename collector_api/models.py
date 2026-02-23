from datetime import datetime
from typing import Optional
from sqlalchemy import JSON, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Relationships
    documents: Mapped[list["Document"]] = relationship(back_populates="dataset")

    def __repr__(self) -> str:
        return f"Dataset(id={self.id}, name={self.name})"


class Scraper(Base):
    __tablename__ = "scrapers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"Scraper(id={self.id}, name={self.name})"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_downloaded: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Foreign keys
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), nullable=False)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="documents")


    def __repr__(self) -> str:
        return f"Document(id={self.id}, title={self.title}, source_url={self.source_url})"
