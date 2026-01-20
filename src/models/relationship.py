"""
Relationship Data Model - Citation relationships between papers
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Relationship:
    """Paper citation relationship data class"""
    source_paper_id: str           # citing paper
    target_paper_id: str           # cited paper
    relationship_type: str = 'cites'  # relationship type
    relationship_desc: Optional[str] = None  # natural language description

    # Relationship type constants
    TYPE_IMPROVES = 'improves'      # improves
    TYPE_BUILDS_ON = 'builds_on'    # builds on
    TYPE_COMPARES = 'compares'      # compares
    TYPE_APPLIES = 'applies'        # applies to
    TYPE_SURVEYS = 'surveys'        # surveys
    TYPE_EXTENDS = 'extends'        # extends
    TYPE_CITES = 'cites'            # cites (default)

    @classmethod
    def get_valid_types(cls) -> list:
        """Get all valid relationship types"""
        return [
            cls.TYPE_IMPROVES,
            cls.TYPE_BUILDS_ON,
            cls.TYPE_COMPARES,
            cls.TYPE_APPLIES,
            cls.TYPE_SURVEYS,
            cls.TYPE_EXTENDS,
            cls.TYPE_CITES
        ]

    @classmethod
    def get_type_description(cls, rel_type: str) -> str:
        """Get relationship type description"""
        descriptions = {
            cls.TYPE_IMPROVES: 'improves',
            cls.TYPE_BUILDS_ON: 'builds on',
            cls.TYPE_COMPARES: 'compares',
            cls.TYPE_APPLIES: 'applies to',
            cls.TYPE_SURVEYS: 'surveys',
            cls.TYPE_EXTENDS: 'extends',
            cls.TYPE_CITES: 'cites'
        }
        return descriptions.get(rel_type, 'cites')

    def to_db_dict(self) -> Dict[str, Any]:
        """
        Convert to database storage format

        Returns:
            Dictionary suitable for database insertion
        """
        return {
            'source_paper_id': self.source_paper_id,
            'target_paper_id': self.target_paper_id,
            'relationship_type': self.relationship_type,
            'relationship_desc': self.relationship_desc
        }

    @classmethod
    def from_db_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """
        Create Relationship object from database record

        Args:
            data: Database query result dictionary

        Returns:
            Relationship object
        """
        return cls(
            source_paper_id=data['source_paper_id'],
            target_paper_id=data['target_paper_id'],
            relationship_type=data.get('relationship_type', cls.TYPE_CITES),
            relationship_desc=data.get('relationship_desc')
        )

    def __str__(self) -> str:
        """Friendly string representation"""
        type_desc = self.get_type_description(self.relationship_type)
        if self.relationship_desc:
            return f"Relationship({self.source_paper_id[:8]}... {type_desc} {self.target_paper_id[:8]}...: {self.relationship_desc})"
        return f"Relationship({self.source_paper_id[:8]}... {type_desc} {self.target_paper_id[:8]}...)"

    def __repr__(self) -> str:
        return self.__str__()


if __name__ == "__main__":
    # Test Relationship model
    print("🍃 Testing Relationship Model")

    # Create basic relationship
    rel1 = Relationship(
        source_paper_id='paper_a_123',
        target_paper_id='paper_b_456',
        relationship_type=Relationship.TYPE_IMPROVES,
        relationship_desc='Paper A improves Paper B training efficiency'
    )

    print(f"\n✅ Relationship created successfully:")
    print(f"   {rel1}")
    print(f"   Type description: {rel1.get_type_description(rel1.relationship_type)}")

    # Test database format conversion
    db_dict = rel1.to_db_dict()
    print(f"\n✅ Database format conversion successful:")
    print(f"   {db_dict}")

    # Test restoring from database
    rel2 = Relationship.from_db_dict(db_dict)
    print(f"\n✅ Restored from database successfully:")
    print(f"   {rel2}")

    # Test all relationship types
    print(f"\n✅ All valid relationship types:")
    for rel_type in Relationship.get_valid_types():
        print(f"   - {rel_type}: {Relationship.get_type_description(rel_type)}")
