# Retriever Specification

**Enterprise Data Intelligence Platform — Hybrid Retrieval Engine**

| Metadata | Value |
|----------|-------|
| **Author** | Principal Retrieval Architect |
| **Date** | 2026-07-10 |
| **Status** | Approved |
| **Version** | 1.0 |
| **Architecture Reference** | System-Architecture.md \u00a73.2, Component-Design.md \u00a74 |
| **Cross-References** | AI-Agent-Specification.md \u00a73, KnowledgeEngine-Specification.md \u00a72-\u00a79, Schema-Specification.md \u00a719, Performance-Specification.md \u00a71, \u00a73, \u00a76, Database-Specification.md \u00a75-\u00a76 |

---

## 1. Retriever Responsibilities

### 1.1 Mission

Given a user query and the available knowledge stores, retrieve the most relevant schema context, business definitions, and query patterns that enable the Planner and Generator to produce correct SQL. The Retriever is the bridge between raw user language and structured database understanding.

### 1.2 Primary Responsibilities

| Responsibility | Description | Failure Mode |
|---------------|-------------|--------------|
| **Schema retrieval** | Find tables and columns relevant to the query | Missing tables cause planner to fail |
| **Semantic search** | Match user intent to schema elements by meaning, not by name | Relevant columns not found |
| **Keyword search** | Exact/partial name matching for known identifiers | Miss obvious matches when embedding fails |
| **Knowledge graph traversal** | Navigate business relationships, join paths, entity hierarchies | Missing business context |
| **Business ontology lookup** | Resolve business terms to physical schema | User terms not mapped to database |
| **Query history retrieval** | Find similar past queries for pattern reuse | Miss optimization opportunities |
| **Context compression** | Fit relevant context within LLM context window | Overwhelm or starve the LLM |
| **Hybrid ranking** | Combine multiple retrieval signals into unified ranking | Poor ranking buries relevant results |
| **Query expansion** | Enrich user query with synonyms and business terms | Narrow retrieval misses relevant columns |

### 1.3 Non-Responsibilities

| Not Responsible For | Handled By |
|--------------------|------------|
| Planning query execution | Query Planner (Planner-Specification.md) |
| Generating SQL | SQL Generator (AI-Agent-Spec.md \u00a75) |
| Validating SQL | Validator Agent (AI-Agent-Spec.md \u00a76) |
| Executing queries | Query Executor (EP-011) |
| Annotating schema elements | Schema Intelligence (Schema-Spec.md) |
| Maintaining knowledge graph | Knowledge Engine (KE-Spec.md \u00a75-\u00a76) |

### 1.4 Architecture Rationale

**Why hybrid retrieval instead of pure vector search?**

Enterprise schemas present unique challenges for retrieval:

1. **Naming sparsity**: Columns named `c1`, `c2`, `txn_amt_01` have weak semantic signal. Embeddings alone cannot disambiguate them.
2. **Business terminology**: Users ask for "revenue" not `total_amount_usd`. The mapping requires ontology lookup, not vector similarity.
3. **Structural relationships**: "Show orders with customer names" requires knowing `orders.customer_id \u2192 customers.id`. This is a graph traversal problem, not a vector search problem.
4. **Precision requirements**: False positives in retrieval cause the Planner to generate plans with wrong tables, wasting downstream compute. High precision is non-negotiable.

The hybrid approach combines four retrieval modalities, each compensating for the others' weaknesses:

| Modality | Strength | Weakness |
|----------|----------|----------|
| **Vector search** | Semantic understanding, fuzzy matching | Blind to structure, poor with rare terms |
| **Keyword search** | Exact matching, high precision | Misses synonyms, no semantics |
| **Metadata retrieval** | Structural relationships, type info | No semantic understanding |
| **Knowledge graph** | Business meaning, entity resolution | Limited to known relationships |

The Retriever uses Reciprocal Rank Fusion (RRF) to combine results from all modalities into a single ranked list. This is the same approach used by commercial search engines (Google, Bing) for combining heterogeneous rankers. RRF is preferred over learned fusion because:
- It requires no training data (cold-start friendly)
- It is transparent and debuggable
- It performs within 5% of learned methods on benchmark evaluations

---

## 2. Retrieval Architecture

### 2.1 Component Diagram

```
User Query
    |
    v
+------------------+
| Query Analyzer   |  Parse query, extract entities, detect intent
+--------+---------+
         |
         +------------------------------------------+
         |                    |                      |
         v                    v                      v
+------------------+  +------------------+  +------------------+
| Vector Search    |  | Keyword Search   |  | Metadata Search  |
| (Qdrant, BGE-M3) |  | (BM25 + inverted) |  | (PostgreSQL)     |
+------------------+  +------------------+  +------------------+
         |                    |                      |
         +------------------------------------------+
                              |
                              v
+------------------+
| Hybrid Ranker   |  RRF fusion of all result sets
+------------------+
         |
         v
+------------------+
| Query Expander  |  Expand query with synonyms, business terms
+------------------+
         |
         v  (expanded query re-runs through vector + keyword)
         |
+------------------+
| KG Traverser    |  Business ontology, entity resolution, join paths
+------------------+
         |
         v
+------------------+
| Reranker        |  Cross-encoder reranking of top-N candidates
+------------------+
         |
         v
+------------------+
| Context Builder |  Compress, format, and order context for LLM
+------------------+
         |
         v
   Retrieved Context (to Planner)
```

### 2.2 Retrieval Flow

```
Phase 1: Initial Retrieval (fast path, < 200ms)
  1. Parse query into structured intent + entities
  2. Execute vector search on schema_columns collection
  3. Execute keyword search on column names + table names
  4. Execute metadata search for exact type/table matches
  5. Fuse results via RRF (k=60)
  6. Return top-20 candidates

Phase 2: Expanded Retrieval (medium path, < 500ms)
  7. Expand query with synonyms from thesaurus
  8. Execute vector + keyword search with expanded terms
  9. Execute knowledge graph traversal for entity resolution
  10. Fuse expanded results via RRF
  11. Return top-30 candidates

Phase 3: Reranking (slow path, < 1s)
  12. Cross-encoder rerank top-30 candidates
  13. Prune to top-15 based on rerank score
  14. Build context package for Planner
```

### 2.3 Context Package Structure

```
RetrievedContext {
    query_id: UUID
    query_analysis: QueryAnalysis {
        intent: string
        entities: [Entity]
        complexity: "simple" | "medium" | "complex"
        estimated_tables: int
    }
    tables: [TableContext {
        table: TableRef
        relevance_score: float
        matched_via: "vector" | "keyword" | "metadata" | "kg" | "expanded"
        columns: [ColumnContext {
            column: ColumnRef
            relevance_score: float
            semantic_type: SemanticType
            description: string
            synonyms: [string]
        }]
        relationships: [RelationshipEdge]
    }]
    business_terms: [BusinessTerm {
        term: string
        resolved_to: ColumnRef
        confidence: float
    }]
    query_history: [SimilarQuery]   // Top 5 similar past queries
    metadata: RetrievalMetadata {
        retrieval_time_ms: int
        modalities_used: [string]
        expansion_applied: bool
        reranked: bool
        total_candidates_considered: int
    }
}
```

---

## 3. Vector Retrieval

### 3.1 Embedding Collections

_Qdrant was removed during cleanup — vector search falls back to PostgreSQL pgvector for embedding storage and retrieval._

### 3.2 Search Configuration

```python
# Pseudocode: vector search configuration
VECTOR_SEARCH_CONFIG = {
    "schema_columns": {
        "limit": 50,
        "score_threshold": 0.45,    # Min cosine similarity
        "hnsw_ef": 128,             # HNSW search breadth
        "exact_search": False,      # Use HNSW approximation
        "payload_filter": {         # Always filter by tenant
            "must": [{"key": "tenant_id", "match": {"value": "{tenant}"}}]
        }
    },
    "schema_tables": {
        "limit": 20,
        "score_threshold": 0.50,
        "hnsw_ef": 64,
        "exact_search": False,
    },
    "query_patterns": {
        "limit": 10,
        "score_threshold": 0.60,
        "hnsw_ef": 64,
        "exact_search": False,
    }
}
```

### 3.3 Hybrid Search (Dense + Sparse)

Each Qdrant collection stores both dense (1024-d BGE-M3) and sparse (SPLADE) vectors. The search combines both:

```
score = alpha * dense_score + (1 - alpha) * sparse_score
where alpha = 0.7 for schema_columns (semantic priority)
      alpha = 0.5 for schema_tables (balanced)
      alpha = 0.8 for query_patterns (semantic priority)
```

**Design decision**: Weighted sum instead of RRF at the individual modality level because dense and sparse scores are from the same system and have comparable distributions. RRF is reserved for cross-modality fusion where score distributions differ fundamentally.

### 3.4 Batch Size and Performance

| Collection | Avg Query Time (P50) | Avg Query Time (P95) | Max QPS Per Pod |
|------------|---------------------|---------------------|-----------------|
| schema_columns | 15ms | 40ms | 500 |
| schema_tables | 10ms | 25ms | 800 |
| query_patterns | 8ms | 20ms | 1000 |
| All three (parallel) | 25ms | 60ms | 200 |

---

## 4. Keyword Retrieval

### 4.1 Index Structure

The keyword index uses BM25 over inverted indexes stored in PostgreSQL:

```
keyword_index (
    id UUID PRIMARY KEY,
    term TEXT NOT NULL,              -- Individual word/token
    entity_type TEXT NOT NULL,       -- 'column_name', 'table_name', 'synonym'
    entity_id UUID NOT NULL,         -- References the schema element
    tenant_id UUID NOT NULL,
    document_frequency INT NOT NULL, -- How many entities contain this term
    term_frequency INT NOT NULL,     -- How many times in this entity
    field_length INT NOT NULL,       -- Length of the name field
    UNIQUE(term, entity_type, entity_id, tenant_id)
)

Indexes:
  - idx_keyword_term ON keyword_index(term, tenant_id)
  - idx_keyword_entity ON keyword_index(entity_id, entity_type)
```

### 4.2 BM25 Scoring

```
BM25 score for term t in entity e:
  IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
  score(t, e) = IDF(t) * (tf(t, e) * (k1 + 1)) / (tf(t, e) + k1 * (1 - b + b * |e| / avgdl))

Where:
  N = total entities
  df(t) = document frequency of term t
  tf(t, e) = term frequency in entity e
  |e| = length of entity field
  avgdl = average field length across all entities
  k1 = 1.2 (term saturation)
  b = 0.75 (length normalization)
```

### 4.3 Tokenization Strategy

| Token Type | Example | Weight Boost |
|------------|---------|--------------|
| Full word | "revenue" | 1.0 |
| Subword (3-gram) | "rev" | 0.3 |
| CamelCase split | "customerId" \u2192 "customer", "id" | 1.0 |
| Snake_case split | "order_total" \u2192 "order", "total" | 1.0 |
| Abbreviation | "qty" \u2192 also matches "quantity" (via synonym index) | 0.8 |
| Digit suffix | "order_2024" \u2192 "order" matches, "2024" matches temporal | 0.5 |
| Prefix match | "cust*" matches "customer", "customers", "cust_id" | 0.7 |

### 4.4 Keyword Query Types

| Query Type | SQL Template | When Used |
|------------|-------------|-----------|
| Exact match | `term = :query` | Known identifier |
| Prefix match | `term LIKE :query || '%'` | Partial name |
| Fuzzy match | `term % :query` (pg_trgm) | Possible typo |
| Multi-term | `term = ANY(:terms)` | Compound names |
| Synonym expansion | Join with synonym table | Common abbreviations |

### 4.5 Performance Targets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Single term lookup | 2ms | 5ms | 10ms |
| Multi-term (5 terms) | 5ms | 15ms | 30ms |
| Synonym expansion + search | 10ms | 25ms | 50ms |
| Fuzzy match | 15ms | 40ms | 80ms |

---

## 5. Metadata Retrieval

### 5.1 Structured Queries

Metadata retrieval uses exact database queries against the schema store for high-precision lookups:

| Query | Purpose | SQL |
|-------|---------|-----|
| Get table by name | Exact match on table name | `SELECT * FROM tables WHERE name = :name AND tenant_id = :tid` |
| Get columns by type | Find columns matching data type | `SELECT * FROM columns WHERE data_type = :type AND tenant_id = :tid` |
| Get columns by semantic type | Find columns of given semantic type | `SELECT * FROM columns WHERE semantic_type = :stype AND tenant_id = :tid` |
| Get FK relationships | Find all FK edges for a table | `SELECT * FROM relationships WHERE source_table_id = :tid OR target_table_id = :tid` |
| Get tables by entity type | Find tables of given business entity | `SELECT * FROM tables WHERE business_entity = :entity AND tenant_id = :tid` |
| Get similar table names | Find tables with similar names | `SELECT *, similarity(name, :name) AS sim FROM tables WHERE tenant_id = :tid ORDER BY sim DESC LIMIT 10` |

### 5.2 When Metadata Retrieval Wins

| Scenario | Why | Vector Search Would Fail |
|----------|-----|------------------------|
| Exact table name known | "orders table" | Embedding may match "orders_view" or "order_history" |
| Data type filter | "date columns" | Vector search returns dates as well as timestamps |
| FK relationships | "joins to customers" | Vector doesn't model relationships |
| Entity type | "customer tables" | May miss tables with non-obvious names |
| Type constraint | "integer columns" | Vector returns any numeric-looking column |

### 5.3 Integration with Vector Search

Metadata results are assigned a synthetic score for RRF fusion:

```
metadata_rrf_score = base_score * confidence_multiplier

base_score:
  - Exact name match:  0.95
  - Exact type match:  0.80
  - Entity match:      0.85
  - Relationship:      0.75  (from known FK)
  - Similar name:      0.60  (pg_trgm similarity)

confidence_multiplier:
  - Exact (indexed column):   1.0
  - Exact (unindexed column): 0.9
  - Semantic type (inferred): 0.8
  - Relationship (inferred):  0.7
  - Similar (fuzzy):          0.5
```

---

## 6. Knowledge Graph Traversal

### 6.1 Graph Structure

The Retriever traverses the Knowledge Graph stored in PostgreSQL (graph_nodes + graph_edges per Database-Specification.md \u00a76):

```
Node Types:
  - TableNode { id, name, entity_type, schema_name, database_id }
  - ColumnNode { id, name, data_type, semantic_type, table_id }
  - BusinessTermNode { id, term, definition, domain }
  - EntityNode { id, entity_type, description }

Edge Types:
  - HAS_COLUMN: Table \u2192 Column
  - FOREIGN_KEY: Column \u2192 Column (with confidence)
  - INFERRED_FK: Column \u2192 Column (with confidence)
  - BELONGS_TO_ENTITY: Table \u2192 Entity
  - MAPS_TO_TERM: Column \u2192 BusinessTerm (with confidence)
  - RELATED_TERM: BusinessTerm \u2192 BusinessTerm
  - JOIN_PATH: Table \u2192 Table (through intermediate tables)
  - HIERARCHY: Entity \u2192 Entity (parent-child)
```

### 6.2 Traversal Algorithms

```
Algorithm A: Entity Resolution
  Input: "revenue" (user term)
  Steps:
    1. Look up BusinessTermNode for "revenue" (and synonyms)
    2. Follow MAPS_TO_TERM edges to ColumnNodes
    3. For each ColumnNode, follow HAS_COLUMN to TableNode
    4. Return { table, column, confidence, path }
  Output:
    - { table: "sales", column: "total_amount", confidence: 0.92 }
    - { table: "orders", column: "order_total", confidence: 0.78 }

Algorithm B: Join Path Discovery
  Input: [orders, customers, products] (tables)
  Steps:
    1. Locate TableNodes for all three tables
    2. BFS from orders, following FOREIGN_KEY + INFERRED_FK edges
    3. Stop when all tables are reachable or max_depth = 5
    4. Return shortest path that connects all tables
  Output:
    - orders.customer_id \u2192 customers.id (FK, conf: 1.0)
    - orders.product_id \u2192 products.id (FK, conf: 1.0)

Algorithm C: Business Hierarchy Traversal
  Input: "electronics products"
  Steps:
    1. Find EntityNode for "product" or similar
    2. Follow HIERARCHY edges to find sub-entities
    3. For each sub-entity, follow BELONGS_TO_ENTITY to TableNodes
    4. Return all matching tables
  Output:
    - { table: "electronics", entity: "product_subcategory" }
    - { table: "phones", entity: "product_subcategory" }
    - { table: "laptops", entity: "product_subcategory" }
```

### 6.3 Traversal Performance

| Operation | P50 | P95 | Max Depth |
|-----------|-----|-----|-----------|
| Business term resolution | 10ms | 25ms | 2 hops |
| Join path discovery (3 tables) | 20ms | 50ms | 5 hops |
| Join path discovery (5 tables) | 50ms | 100ms | 5 hops |
| Entity hierarchy traversal | 15ms | 40ms | 3 hops |
| Full graph traversal (all connected tables) | 100ms | 300ms | 5 hops |

---

## 7. Business Ontology Lookup

### 7.1 Ontology Structure

The business ontology is a curated hierarchy of business terms maintained in the Knowledge Graph:

```
Domain: Sales
  +-- Revenue
  |   +-- Gross Revenue -> maps to sales.total_amount
  |   +-- Net Revenue -> maps to sales.net_amount
  |   +-- Recurring Revenue -> maps to subscriptions.mrr
  +-- Customer
  |   +-- Acquisition Cost -> maps to marketing.cac
  |   +-- Lifetime Value -> maps to analytics.customer_ltv
  +-- Pipeline
      +-- Deal Value -> maps to crm.deal_amount
      +-- Win Rate -> maps to analytics.win_rate

Domain: Finance
  +-- Expenses
  |   +-- COGS -> maps to finance.cogs
  |   +-- OPEX -> maps to finance.operating_expenses
  +-- Profit
      +-- Gross Profit -> formula: Gross Revenue - COGS
      +-- Net Profit -> formula: Net Revenue - Total Expenses
```

### 7.2 Lookup Process

```
Input: User query tokens
Output: Resolved business terms with column mappings

Process:
1. Tokenize query into candidate terms (n-grams: 1, 2, 3)
2. For each candidate, search ontology index (Qdrant + PostgreSQL)
   - Qdrant: vector similarity against term definitions
   - PostgreSQL: exact + fuzzy match against term names
3. Rank candidates by confidence (= max of vector score, term match score)
4. For top-5 candidates:
   - Follow MAPS_TO_TERM edges to physical columns
   - If term is a computed metric (formula-based):
     - Return the formula definition
     - Flag for Planner as "computed metric, not a column"
5. Return resolved terms with column mappings + confidence
```

### 7.3 Ontology Confidence Scoring

| Match Type | Confidence | Example |
|------------|------------|---------|
| Exact term name match | 0.95 | "revenue" \u2192 Revenue |
| Synonym match | 0.85 | "turnover" \u2192 Revenue |
| Fuzzy name match (pg_trgm > 0.6) | 0.70 | "revenoo" \u2192 Revenue |
| Vector similarity > 0.75 | 0.65 | "money made" \u2192 Revenue |
| Compound term match | 0.80 | "gross revenue" \u2192 Gross Revenue |
| Formula-derived term | 0.60 | "profit margin" \u2192 (revenue - cost) / revenue |
| Cross-domain match | 0.50 | "revenue" in Marketing context |

---

## 8. Hybrid Ranking

### 8.1 Reciprocal Rank Fusion (RRF)

The Retriever combines results from all retrieval modalities using RRF:

```
RRF_score(d) = SUM over all result sets R of 1 / (k + rank_R(d))

Where:
  d = a document (table or column)
  R = result set from a retrieval modality
  rank_R(d) = rank position of d in result set R
  k = 60 (standard RRF constant, mitigates impact of high rankings)
```

### 8.2 Result Set Weighting

Each modality contributes to the final RRF score with equal weight by default. Per-query-type weights can be tuned:

| Query Type | Vector | Keyword | Metadata | KG | Expansion |
|------------|--------|---------|----------|-----|-----------|
| SIMPLE_SELECT | 0.50 | 0.30 | 0.10 | 0.10 | 0.00 |
| JOIN | 0.25 | 0.20 | 0.20 | 0.35 | 0.00 |
| AGGREGATION | 0.40 | 0.20 | 0.25 | 0.15 | 0.00 |
| COMPOUND | 0.30 | 0.20 | 0.15 | 0.25 | 0.10 |
| AMBIGUOUS | 0.35 | 0.25 | 0.10 | 0.20 | 0.10 |
| CROSS_DB | 0.20 | 0.20 | 0.30 | 0.30 | 0.00 |

**Design decision**: RRF with per-type weights vs learned fusion. RRF is chosen because:
- Zero training data required (cold-start friendly)
- Interpretable (each modality's contribution visible)
- Stable across schema changes (no retraining needed)
- Within 5% of LambdaRank on internal benchmarks

Per-type weights are manually tuned heuristics. They can be replaced by learned weights after sufficient query history accumulates (post-MVP).

### 8.3 Fusion Pipeline

```
1. Execute all enabled retrieval modalities in parallel
2. Collect result sets: R_vector, R_keyword, R_metadata, R_kg, R_expansion
3. For each result set, assign rank positions (1-indexed)
4. Compute RRF score for each unique document
5. Apply query-type weights to modality scores
6. Sort by weighted RRF score descending
7. Return top-K candidates (K = 30 for phase 1, K = 50 for phase 2)
```

### 8.4 Score Normalization

Before fusion, ensure scores from different modalities are comparable:

```
Normalized score = (raw_score - modality_min) / (modality_max - modality_min)

Where modality_min and modality_max are tracked per modality per tenant.
Updated every 100 queries via streaming statistics.
```

---

## 9. Context Compression

### 9.1 Compression Strategies

The Retriever must fit relevant context within the LLM's context window. Compression is applied in order:

```
Strategy 1: Column pruning (aggressive)
  - For each table, keep only columns relevant to the query
  - Relevance determined by: semantic type match, name similarity, FK participation
  - Drop columns with no plausible relevance (irrelevant timestamps, internal IDs)
  - Compression ratio: ~70% (e.g., 50 columns \u2192 15 columns)

Strategy 2: Description truncation (moderate)
  - Truncate column descriptions to 100 characters
  - Prefix with column name (always preserved)
  - Compression ratio: ~40% (long descriptions)

Strategy 3: Table pruning (conservative)
  - Remove tables with relevance score < 0.3
  - Keep at least the top-3 tables regardless
  - Compression ratio: ~30% (irrelevant tables)

Strategy 4: Relationship compression (light)
  - Include only direct FK relationships between kept tables
  - Omit inferred relationships with confidence < 0.6
  - Compression ratio: ~50% (relationship edges)

Strategy 5: Synonym compression
  - Include only top-3 synonyms per column
  - Prefer synonyms that match query terms
  - Drop redundant synonyms
  - Compression ratio: ~60% (synonym lists)
```

### 9.2 Compression Order

```
Applied sequentially, stopping when context fits within limit:

1. Apply Strategy 3 (table pruning)        -- drops irrelevant tables
2. Apply Strategy 1 (column pruning)       -- drops irrelevant columns
3. Apply Strategy 4 (relationship pruning) -- drops low-confidence edges
4. Apply Strategy 5 (synonym pruning)      -- drops redundant synonyms
5. Apply Strategy 2 (description trunc)    -- shortens descriptions

If context still exceeds limit after all strategies:
  - Reduce top-K tables to 3
  - Reduce columns per table to 10
  - Flag as "truncated context" in retrieval metadata
```

### 9.3 Context Window Budget

```
Total context budget: 8000 tokens (for the context portion)

Allocation by complexity:

Simple query (1-2 tables):
  - Table definitions:      2000 tokens  (2 tables x 1000)
  - Column definitions:     2000 tokens  (2 tables x 20 cols x 50 tok)
  - Relationships:           500 tokens
  - Query history:          500 tokens
  - Total:                 5000 tokens

Medium query (3-5 tables):
  - Table definitions:      3000 tokens  (3 tables x 1000)
  - Column definitions:     3000 tokens  (3 tables x 20 cols x 50 tok)
  - Relationships:          1000 tokens
  - Query history:          500 tokens
  - Total:                 7500 tokens

Complex query (6+ tables):
  - Table definitions:      3000 tokens  (3 key tables x 1000)
  - Column definitions:     3000 tokens  (3 tables x 20 cols x 50 tok)
  - Relationships:          1000 tokens
  - Query history:          500 tokens
  - Total:                 7500 tokens (tables beyond 3 are compressed)
```

---

## 10. Context Window Optimization

### 10.1 Token Budget Management

```python
# Pseudocode: token budget manager
class TokenBudgetManager:
    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.allocations = []

    def allocate(self, component: str, tokens: int, priority: int):
        """Request token allocation for a component. Priority 1 = highest."""
        self.allocations.append({
            "component": component, "tokens": tokens, "priority": priority
        })

    def resolve(self) -> list[Allocation]:
        """Resolve allocations against budget. High priority first."""
        sorted_allocations = sorted(self.allocations, key=lambda a: a["priority"])
        result = []
        remaining = self.max_tokens

        for alloc in sorted_allocations:
            if alloc["tokens"] <= remaining:
                result.append(alloc)
                remaining -= alloc["tokens"]
            else:
                # Truncate this allocation
                truncated = truncate_component(alloc["component"], remaining)
                result.append(truncated)
                break

        return result
```

### 10.2 Priority Allocation

| Component | Priority | Default Tokens | Can Truncate? | Strategy |
|-----------|----------|---------------|---------------|----------|
| Column names | 1 (essential) | 2000 | No | Always include |
| Column data types | 1 (essential) | 500 | No | Always include |
| Matching columns (score > 0.8) | 2 (critical) | 1500 | No | Include all |
| Table names | 3 (important) | 500 | Yes | Keep top 5 |
| Column descriptions | 4 (helpful) | 1000 | Yes | Truncate to 50 chars |
| Relationships | 5 (contextual) | 1000 | Yes | Keep direct FKs only |
| Synonyms | 6 (supplemental) | 500 | Yes | Top 3 per column |
| Query history | 7 (nice-to-have) | 500 | Yes | Keep top 2 |
| Business terms | 8 (expanding) | 500 | Yes | Remove if over budget |

### 10.3 Progressive Disclosure

The context is structured so the LLM sees essential information first:

```
Context Template (token-optimized):

[TABLE: {name}] ({entity_type}) -- {description_truncated}
  Columns:
  - {name}: {type} [{semantic_type}] {'DESCRIPTION' if confidence > 0.7 else ''}
  - {name}: {type} [{semantic_type}] ...

[RELATIONSHIPS (DIRECT ONLY)]
  {table}.{col} -> {target}.{col} [{type}, conf={confidence}]

[RELEVANT BUSINESS TERMS]
  {term} -> {table}.{column} (conf={confidence})

[PREVIOUS QUERIES]
  Q: {similar_query}
  SQL: {similar_sql}

[END CONTEXT]
```

---

## 11. Reranking

### 11.1 Cross-Encoder Reranking

After initial retrieval (top-50 candidates), a cross-encoder model reranks the candidates for precision:

```
Input: Query + (table_name, column_name, description, data_type)
       (50 candidates x 1 pair each = 50 inference calls)
Output: Relevance score (0.0 - 1.0) for each candidate

Model: BGE-reranker-v2-m3 (or miniLM-cross-encoder)
Batch size: 16
Precision improvement: +15-25% over RRF alone
Latency: ~20ms per batch of 16 (GPU)
           ~80ms per batch of 16 (CPU)
```

**Design decision**: Cross-encoder vs LLM-as-reranker. Cross-encoders are preferred because:
- 10-50x faster than LLM reranking
- Specifically trained for relevance scoring
- No prompt engineering needed
- Consistent scoring across queries

### 11.2 Reranking Flow

```
1. Take top-50 candidates from hybrid RRF fusion
2. Batch query + candidate pairs (batch size = 16)
3. Run cross-encoder inference
4. Apply score normalization (min-max scaling across batch)
5. Combine with RRF score: final_score = 0.6 * rerank_score + 0.4 * rrf_score
6. Re-sort by final_score
7. Keep top-15 candidates
8. If rerank confidence < 0.5 for all candidates, fall back to RRF-only ordering
```

### 11.3 When to Skip Reranking

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Batch size < 5 | Skip reranking | Too few candidates to benefit |
| RRF top-1 score > 0.95 | Skip reranking | First result is clearly correct |
| Query is SIMPLE_SELECT | Skip reranking | Simple queries don't need reranking |
| Latency budget exceeded | Skip reranking | RRF-only is acceptable fallback |
| Reranker model unavailable | Skip reranking | Degrade gracefully |

---

## 12. Embedding Strategy

### 12.1 Embedding Model: BGE-M3

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | BAAI/bge-m3 | Best open-source multilingual embedder |
| Dimensions | 1024 (dense) + sparse | Hybrid search capability |
| Max tokens | 8192 | Handles long descriptions |
| Normalization | L2-normalized | Cosine similarity with normalized vectors |
| Precision | FP16 | 2x speed, negligible accuracy loss |
| Batch size | 128 | Optimal throughput on MI300X |
| Hardware | GPU (MI300X) or CPU fallback | Primary: GPU for < 10ms latency |

### 12.2 What Gets Embedded

| Entity | Embedding Text | Update Trigger | Priority |
|--------|---------------|----------------|----------|
| Column | `{name}: {description} [{semantic_type}]` | Schema sync, annotation | High |
| Table | `{name} ({entity_type}): {description}` | Schema sync | High |
| Business term | `{term}: {definition} [{domain}]` | Glossary import | Medium |
| Query pattern | `{query_text} -> {sql_text}` | After successful execution | Low |
| Synonym | `{synonym} -> {original_column}` | Synonym generation | Medium |

### 12.3 Embedding Update Strategy

```
Fresh schema:  Full re-embed on first sync (blocks until complete)
Schema change: Re-embed only changed columns (incremental)
Business term: Re-embed on import or update
Query history: Batch re-embed every hour (rolling window)
Synonym:       Re-embed on generation
```

### 12.4 Embedding Cost Budget

| Operation | Volume | GPU Time | Cost (GPU @ $0.02/hr) |
|-----------|--------|----------|----------------------|
| Initial sync (200 tables, 3000 columns) | ~3200 items | ~6s | ~$0.00003 |
| Incremental sync (10 changed columns) | ~10 items | ~2ms | ~$0.00000001 |
| Query embedding (single) | 1 item | ~2ms | ~$0.00000001 |
| Batch query embedding (100 queries) | 100 items | ~20ms | ~$0.0000001 |
| Business glossary import (500 terms) | 500 items | ~100ms | ~$0.0000005 |
| Daily total (1000 active queries) | ~5000 items/day | ~1s/day | ~$0.000005/day |

---

## 13. Query Expansion

### 13.1 Expansion Sources

| Source | Expansion Type | Example | Confidence Impact |
|--------|---------------|---------|-------------------|
| Column synonyms | `cust_id` \u2192 `customer_id, customer_identifier` | +5-15% recall | High |
| Business term synonyms | `revenue` \u2192 `sales, income, turnover` | +10-20% recall | High |
| Common abbreviations | `qty` \u2192 `quantity`, `dept` \u2192 `department` | +5-10% recall | Medium |
| Acronym expansion | `sku` \u2192 `stock_keeping_unit` | +2-5% recall | Medium |
| Acronym generation | `stock_keeping_unit` \u2192 `sku` | +2-5% recall | Medium |
| Domain-specific thesaurus | `client` \u2192 `customer`, `employee` \u2192 `staff` | +5-10% recall | Medium |
| LLM-generated synonyms | `buyers` \u2192 `customers, clients, purchasers` | +5-15% recall | Low (LLM call) |

### 13.2 Expansion Pipeline

```
Input: User query tokens
Output: Expanded token set

Algorithm:
1. Tokenize query into individual terms
2. For each term:
   a. Look up synonym index (Qdrant + PostgreSQL)
   b. If exact match found: add all synonyms with confidence > 0.7
   c. If no exact match: try fuzzy match (pg_trgm similarity > 0.6)
   d. If no fuzzy match: try abbreviation/acronym expansion
   e. If no match: keep original term
3. For each business term match:
   a. Add the physical column name(s) it maps to
   b. Add related business terms (from ontology)
4. Deduplicate expanded set
5. Score each expansion by confidence of source
6. Filter expansions with confidence < 0.5
7. Add top-5 expansions per original query term
```

### 13.3 When to Expand

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Initial retrieval returns < 10 candidates | Full expansion | Need more candidates |
| Query contains known abbreviation | Targeted expansion | qty \u2192 quantity |
| Query contains business term | Ontology expansion | revenue \u2192 sales column |
| Query matches known acronym pattern | Acronym expansion | SKU \u2192 stock_keeping_unit |
| First retrieval had low confidence (< 0.5) | Full expansion | Need better candidates |
| Query is SIMPLE_SELECT with known table | Skip expansion | Direct lookup is sufficient |

---

## 14. Cache Strategy

### 14.1 Cache Layers

| Layer | Technology | TTL | Content | Invalidation |
|-------|------------|-----|---------|-------------|
| L1: In-memory (local) | Dict (per pod) | 60s | Recent retrieval results (top-100) | TTL expiry, schema change event |
| L2: Distributed (PostgreSQL) | PostgreSQL | 300s | Frequent retrieval results | TTL expiry, schema change event |
| L3: Embedding cache | PostgreSQL | 3600s | Computed query embeddings | TTL expiry |
| L4: Result cache | PostgreSQL | 600s | Frequently requested schemas | Schema version change |

### 14.2 Cache Keys

```python
# Pseudocode: cache key structure
CACHE_KEY_TEMPLATES = {
    "vector_search": "ret:v:{tenant}:{collection}:{query_hash}:{limit}",
    "keyword_search": "ret:k:{tenant}:{query_hash}:{limit}",
    "metadata_search": "ret:m:{tenant}:{query_type}:{params_hash}",
    "kg_traversal": "ret:g:{tenant}:{start_node}:{depth}:{algorithm}",
    "ontology_lookup": "ret:o:{tenant}:{term}:{domain}",
    "embedding": "ret:e:{tenant}:{text_hash}",
    "rrf_fusion": "ret:rrf:{tenant}:{query_hash}:{modalities_hash}",
    "rerank": "ret:rr:{tenant}:{query_hash}:{candidates_hash}",
}
```

### 14.3 Cache Hit Ratio Targets

| Cache Layer | Target Hit Ratio | Latency Saved | Impact |
|-------------|-----------------|---------------|--------|
| L1: In-memory | 20% | ~50ms | Fastest queries |
| L2: PostgreSQL | 30% | ~40ms | Common queries |
| L3: PostgreSQL (embedding) | 50% | ~5ms | Query embedding hits |
| L4: PostgreSQL (schema) | 15% | ~100ms | Schema-heavy queries |
| **Composite** | **~60%** | **~50ms avg** | Overall user experience |

### 14.4 Cache Warmup

On pod startup and after schema changes:

```
Warmup sequence:
1. Identify the 100 most frequent queries (from query history)
2. Pre-compute embeddings for these queries (L3 cache)
3. Pre-execute retrieval for these queries (L2 cache)
4. Pre-compute RRF fusion results (L2 cache)

Warmup latency: ~10 seconds
Warmup frequency: On pod deploy, on schema change for top-10 tables
```

---

## 15. Failure Handling

### 15.1 Failure Modes

| Failure | Detection | Impact | Mitigation |
|---------|-----------|--------|------------|
| **Qdrant unavailable** | Connection timeout | Vector search fails | Fall back to keyword + metadata only |
| **PostgreSQL unavailable** | Connection timeout | Metadata + KG fail | Fall back to vector + keyword only |
| **Embedding service down** | Embedding timeout | No query embedding | Use cached embedding or skip vector search |
| **BM25 index stale** | New tables not in index | Missing from keyword results | Trigger index rebuild, use vector fallback |
| **Cross-encoder down** | Inference timeout | No reranking | Use RRF-only results |
| **LLM expansion fails** | LLM timeout | No LLM-based expansion | Use synonym-based expansion only |
| **Cache unavailable** | Redis connection timeout | No caching | Direct retrieval (slower but functional) |
| **Context too large** | Token count > limit | Truncated context | Apply aggressive compression |
| **Empty results** | No candidates found | Failed retrieval | Return empty context, Planner handles gracefully |
| **Result limit exceeded** | > 5000 candidates | Memory pressure | Cap at 500 candidates, log warning |

### 15.2 Degraded Mode Behavior

| Degraded State | Operation | Quality Impact | User Impact |
|----------------|-----------|---------------|-------------|
| Vector search down | Keyword + metadata + KG only | Recall drops ~30% | May miss semantically matched columns |
| KG unavailable | Vector + keyword + metadata only | Business context lost | Business terms not resolved |
| Metadata search down | Vector + keyword + KG only | No exact type/entity matches | Type-based filtering unavailable |
| Reranker unavailable | RRF-only fusion | Precision drops ~15% | More irrelevant results in context |
| Cache down | Full retrieval (no cache) | Latency increases ~50ms | Slightly slower queries |
| Expansion unavailable | Non-expanded retrieval | Recall drops ~10% | May miss synonym-matched columns |

### 15.3 Health Checks

_Redis and Qdrant health checks were removed during cleanup — PostgreSQL serves as the primary data store._

---

## 16. Latency Optimization

### 16.1 Latency Budget

| Phase | Operation | P50 Budget | P95 Budget | P99 Budget |
|-------|-----------|------------|------------|------------|
| Phase 1 | Query parsing + entity extraction | 20ms | 50ms | 100ms |
| Phase 1 | Vector search (3 collections, parallel) | 25ms | 60ms | 100ms |
| Phase 1 | Keyword search (BM25) | 15ms | 40ms | 80ms |
| Phase 1 | Metadata search | 10ms | 25ms | 50ms |
| Phase 1 | RRF fusion (3 result sets) | 5ms | 10ms | 20ms |
| Phase 1 | **Total** | **75ms** | **185ms** | **350ms** |
| Phase 2 | Query expansion | 10ms | 25ms | 50ms |
| Phase 2 | Re-run vector + keyword (expanded) | 25ms | 60ms | 100ms |
| Phase 2 | KG traversal | 25ms | 50ms | 100ms |
| Phase 2 | RRF fusion (5 result sets) | 10ms | 20ms | 40ms |
| Phase 2 | **Total** | **70ms** | **155ms** | **290ms** |
| Phase 3 | Cross-encoder reranking (50 -> 15) | 100ms | 200ms | 400ms |
| Phase 3 | Context compression | 5ms | 10ms | 20ms |
| Phase 3 | **Total** | **105ms** | **210ms** | **420ms** |
| **End-to-end** | All phases | **250ms** | **550ms** | **1.06s** |

### 16.2 Optimization Techniques

| Technique | Impact | Complexity | Where Applied |
|-----------|--------|------------|---------------|
| Parallel execution of independent retrievers | 3x speedup | Low | Phase 1 (all searches in parallel) |
| HNSW index (ef=128) | 10x vs brute force | None (index built) | Vector search |
| Connection pooling (KE API) | 50ms reduction | Low | All KE-dependent operations |
| Batch embedding | 4x throughput | Medium | Embedding requests |
| Async I/O (asyncio) | 2x concurrent capacity | Low | All external calls |
| Sparse-dense hybrid skip | Skip vector search if keyword returns high-confidence match | 25ms average saving | Phase 1 entry |
| Early termination | Stop if RRF top-3 confidence > 0.95 | 200ms average saving | Phase 2 entry |
| Stale read for KG | Read replicas for KG traversal | 10ms reduction | KG queries |
| Result caching (L1-L4) | 50ms average saving | Low | All phases |

### 16.3 Early Termination Rules

```python
# Pseudocode: early termination decision
def should_terminate_early(phase_1_results):
    if len(phase_1_results) < 3:
        return False  # Need more candidates
    if phase_1_results[0].rrf_score > 0.95:
        return True   # Confident top result
    if phase_1_results[0].rrf_score - phase_1_results[1].rrf_score > 0.3:
        return True   # Clear winner
    if phase_1_results[:3].all_have("vector_match_score", lambda s: s > 0.9):
        return True   # All top-3 are strong vector matches
    return False      # Need more refinement
```

---

## 17. Multi-Tenant Retrieval

### 17.1 Isolation Mechanisms

| Resource | Isolation | Mechanism |
|----------|-----------|-----------|
| Vector collections | Per-tenant | `{tenant_id}_schema_columns`, `{tenant_id}_schema_tables`, `{tenant_id}_query_patterns` |
| Keyword indexes | Per-tenant | `keyword_index.tenant_id` filter on every query |
| Metadata queries | Per-tenant | `WHERE tenant_id = :tid` on every query |
| Knowledge graph | Per-tenant | `graph_nodes.tenant_id` + `graph_edges.tenant_id` filters |
| Cache | Per-tenant | `ret:{tenant_id}:...` cache key prefix |
| Reranker | Shared (tenant-unaware) | Input contains only tenant's data; no cross-tenant leakage possible |
| Embedding | Shared | Embedding model is stateless; no tenant data retained |

### 17.2 Tenant-Level Configuration

```python
# Pseudocode: per-tenant retrieval configuration
TENANT_RETRIEVAL_CONFIG = {
    "free": {
        "max_candidates": 20,
        "rerank_enabled": False,
        "expansion_enabled": False,
        "kg_traversal_enabled": False,
        "max_cache_ttl": 300,
    },
    "starter": {
        "max_candidates": 30,
        "rerank_enabled": True,
        "expansion_enabled": True,
        "kg_traversal_enabled": True,
        "max_cache_ttl": 600,
    },
    "pro": {
        "max_candidates": 50,
        "rerank_enabled": True,
        "expansion_enabled": True,
        "kg_traversal_enabled": True,
        "max_cache_ttl": 1200,
    },
    "enterprise": {
        "max_candidates": 100,
        "rerank_enabled": True,
        "expansion_enabled": True,
        "kg_traversal_enabled": True,
        "max_cache_ttl": 3600,
    },
}
```

### 17.3 Cross-Tenant Isolation Validation

- [ ] Tenant A's vector search never returns Tenant B's columns
- [ ] Tenant A's keyword search never matches Tenant B's table names
- [ ] Tenant A's KG traversal stays within Tenant A's graph nodes
- [ ] Cache keys include tenant_id; Tenant A cannot read Tenant B's cache
- [ ] Reranker receives only Tenant A's candidates
- [ ] Embedding model is stateless; no tenant data retained after inference

---

## 18. APIs

### 18.1 Internal Retriever API (Port 8500, Internal)

| Endpoint | Method | Description | Request | Response |
|----------|--------|-------------|---------|----------|
| /v1/retrieve | POST | Full retrieval pipeline (all phases) | Query + filters | RetrievedContext |
| /v1/retrieve/fast | POST | Phase 1 only (fast path) | Query + filters | RetrievedContext (preliminary) |
| /v1/retrieve/expand | POST | Query expansion only | Query | ExpandedQuery |
| /v1/retrieve/search/vector | POST | Vector search only | Query + collection | SearchResult[] |
| /v1/retrieve/search/keyword | POST | Keyword search only | Query | SearchResult[] |
| /v1/retrieve/search/metadata | POST | Metadata search only | Query + type | SearchResult[] |
| /v1/retrieve/traverse/kg | POST | KG traversal | start_node + depth | GraphPath[] |
| /v1/retrieve/resolve/ontology | POST | Business term resolution | Term + domain | TermResolution[] |
| /v1/retrieve/rerank | POST | Rerank candidates | Query + candidates | RerankedCandidate[] |
| /v1/retrieve/context | POST | Build context package | Retrieved data | RetrievedContext |
| /v1/retrieve/cache/status | GET | Cache hit rates | - | CacheStatus |
| /v1/retrieve/cache/warmup | POST | Warmup caches | - | WarmupStatus |
| /v1/retrieve/health | GET | Health check | - | HealthStatus |

### 18.2 Event API

| Event | Emitter | Payload | Subscribers |
|-------|---------|---------|-------------|
| retrieval.completed | Retriever | { query_id, duration_ms, modalities, candidates } | Metrics, tracing |
| retrieval.failed | Retriever | { query_id, error_code, fallback_used } | Alerting |
| retrieval.empty | Retriever | { query_id, query_text } | Planner (empty context) |
| retrieval.expanded | Retriever | { query_id, original, expanded, expansions_added } | Metrics |
| retrieval.cache_miss | Retriever | { layer, key, duration_ms } | Cache optimization |
| retrieval.slow | Retriever | { query_id, duration_ms, threshold_ms } | Alerting (P99 exceeded) |

### 18.3 Integration with KE API

The Retriever is the primary consumer of the Knowledge Engine API:

```
KE API Call                            Retriever Usage
────────────────────────────────────────────────────────────────
POST /v1/ke/retrieve                  Primary vector search endpoint
GET /v1/ke/schema/table/{id}          Metadata retrieval (single table)
POST /v1/ke/schema/resolve            Business term resolution
POST /v1/ke/query                     KG traversal via structured query
GET /v1/ke/history                    Similar query history retrieval
```

---

## 19. Metrics

### 19.1 Key Metrics

| Metric | Type | Description | Alert Threshold |
|--------|------|-------------|----------------|
| retriever_queries_total | Counter | Total retrieval requests | - |
| retriever_duration_ms | Histogram | End-to-end retrieval time | P95 > 550ms |
| retriever_phase_duration | Histogram | Duration per phase (1, 2, 3) | P95 > budget |
| retriever_modalities_used | Histogram | How many modalities per query | < 2 suggests fallback |
| retriever_candidates_found | Histogram | Candidates returned | < 5 suggests poor recall |
| retriever_early_termination_rate | Gauge | % of queries terminating early | < 10% suggests high complexity |
| retriever_empty_results_rate | Gauge | % of queries with 0 results | > 5% suggests recall issue |
| retriever_fallback_rate | Gauge | % of queries using degraded mode | > 10% suggests infrastructure issue |
| retriever_expansion_rate | Gauge | % of queries where expansion triggered | < 20% suggests expansion underused |
| retriever_rerank_rate | Gauge | % of queries where reranking applied | < 50% suggests reranker issue |
| retriever_cache_hit_ratio | Gauge | Composite cache hit rate | < 40% suggests cache issue |
| retriever_context_compression_ratio | Histogram | Compressed / uncompressed token ratio | < 0.3 suggests over-compression |
| retriever_context_tokens | Histogram | Context token count | > 7500 suggests budget exceeded |
| retriever_vector_search_latency | Histogram | Qdrant search latency per collection | P95 > 60ms |
| retriever_keyword_search_latency | Histogram | BM25 search latency | P95 > 40ms |
| retriever_kg_traversal_latency | Histogram | KG traversal latency | P95 > 100ms |
| retriever_rerank_latency | Histogram | Cross-encoder rerank latency | P95 > 400ms |
| retriever_embedding_latency | Histogram | Query embedding latency | P95 > 20ms |

### 19.2 Quality Metrics

| Metric | Description | Collection Method | Target |
|--------|-------------|-------------------|--------|
| **Recall@10** | Relevant columns in top-10 | Human evaluation + feedback | > 80% |
| **Recall@30** | Relevant columns in top-30 | Human evaluation + feedback | > 90% |
| **Precision@10** | % of top-10 that are relevant | Human evaluation + feedback | > 70% |
| **MRR** | Mean reciprocal rank of first relevant | Implicit (query success) | > 0.85 |
| **NDCG@10** | Normalized discounted cumulative gain | Human evaluation | > 0.75 |
| **Fallout rate** | Irrelevant columns in context | User feedback (negative) | < 10% |
| **Context usefulness** | User rating of retrieved context | Explicit feedback (1-5) | > 3.5 avg |

### 19.3 Dashboards

```
Dashboard: Retrieval Performance
  - Retrieval latency (P50/P95/P99) over time
  - Phase breakdown (Phase 1 vs 2 vs 3)
  - Modality usage distribution
  - Cache hit ratio by layer
  - Early termination rate
  - Fallback rate by component

Dashboard: Retrieval Quality
  - Recall@10 / Recall@30 over time
  - Precision@10 trend
  - Empty results rate
  - Expansion usage rate
  - Context compression ratio
  - Context token count distribution

Dashboard: Retrieval Health
  - Qdrant health status
  - PostgreSQL health status
  - Embedder health status
  - Reranker health status
  - Cache health status
  - Error rate by modality
```

---

## 20. Benchmarks

### 20.1 Internal Benchmark Suite

| Benchmark | Queries | Tables | Focus | Baseline | Target |
|-----------|---------|--------|-------|----------|--------|
| **Simple Name Match** | 500 | 100 | Exact match: "find customers table" | BM25: 95% | 99% |
| **Synonym Match** | 500 | 100 | Synonym: "show clients" -> customers | BM25: 60% | 85% |
| **Entity Resolution** | 300 | 100 | "find revenue" -> sales.amount | Vector: 70% | 85% |
| **Join Path** | 200 | 200 | "orders with products" -> 3-table join | KG: 80% | 90% |
| **Cross-DB** | 100 | 50 | "compare sales across DBs" | Vector: 40% | 60% |
| **Ambiguous** | 200 | 100 | "Show total by type" (ambiguous) | LLM: 50% | 70% |
| **Cryptic Naming** | 300 | 100 | "t1.c1, t2.c2" -> real schemas | BM25: 30% | 60% |
| **Large Schema** | 200 | 5000 | Find right table among 5000 | Vector: 75% | 85% |
| **Cold Start** | 100 | 200 | No query history, empty caches | RRF: 60% | 75% |
| **Adversarial** | 100 | 100 | Deliberately misleading queries | All: 40% | 55% |

### 20.2 Benchmark Protocol

```
Standard benchmark protocol:

1. Seed environment with known schema (tables + columns + relationships)
2. Clear all caches (L1-L4)
3. Warm up embedder and reranker
4. For each query in benchmark:
   a. Execute retrieval pipeline
   b. Record: latency, candidates found, RRF scores, rerank scores
   c. Compare top-10 candidates against ground truth
   d. Compute: Recall@10, Precision@10, MRR, NDCG@10
5. Repeat 3x and take median
6. Compare against baseline (BM25-only, vector-only, RRF-only)
```

### 20.3 Benchmark Results (Expected)

| Benchmark | Vector Only | BM25 Only | RRF (no rerank) | Full Pipeline | Improvement vs RRF |
|-----------|-------------|-----------|-----------------|---------------|-------------------|
| Simple Name Match | 92% | 95% | 96% | 97% | +1% |
| Synonym Match | 82% | 60% | 85% | 92% | +7% |
| Entity Resolution | 78% | 55% | 80% | 88% | +8% |
| Join Path | 45% | 50% | 65% | 85% | +20% |
| Cross-DB | 40% | 35% | 48% | 55% | +7% |
| Ambiguous | 60% | 40% | 62% | 72% | +10% |
| Cryptic Naming | 55% | 30% | 58% | 65% | +7% |
| Large Schema | 75% | 50% | 78% | 86% | +8% |
| Cold Start | 55% | 45% | 60% | 65% | +5% |
| Adversarial | 35% | 25% | 40% | 50% | +10% |

---

## 21. Testing

### 21.1 Test Levels

| Level | Scope | Framework | Coverage Target |
|-------|-------|-----------|----------------|
| **Unit** | Individual retrievers (vector, keyword, metadata, KG) | pytest | > 90% line |
| **Integration** | Full pipeline with real Qdrant + PostgreSQL | pytest + testcontainers | > 80% path |
| **E2E** | End-to-end retrieval from query to context package | pytest | All 20+ test scenarios |
| **Benchmark** | Recall@10, Precision@10, MRR against ground truth | pytest + custom harness | Targets per benchmark |
| **Performance** | Latency budgets, throughput targets | k6 | P50/P95 within budget |
| **Resilience** | Component failures, degraded modes | Chaos Mesh | Graceful degradation |

### 21.2 Test Scenarios

```
Vector Search Tests:
  - vector_search_exact_name: "customer_id" matches column named "customer_id"
  - vector_search_semantic_match: "client identifier" matches "customer_id"
  - vector_search_partial_match: "cust" matches "customer_id", "cust_name"
  - vector_search_no_match: "quantum flux capacitor" returns empty
  - vector_search_multi_collection: Queries all 3 collections in parallel
  - vector_search_score_threshold: Results below threshold filtered out
  - vector_search_tenant_isolation: Tenant A query returns only Tenant A results

Keyword Search Tests:
  - keyword_exact_match: "orders" matches table name exactly
  - keyword_prefix_match: "ord*" matches "orders", "order_items"
  - keyword_camelcase_split: "customerId" matches "customer", "Id"
  - keyword_snakecase_split: "order_total" matches "order", "total"
  - keyword_fuzzy_match: "costemer" matches "customer" (pg_trgm)
  - keyword_synonym_expansion: "qty" matches "quantity" columns
  - keyword_multi_term: "customer order total" matches across terms

Metadata Search Tests:
  - metadata_exact_table: Known table name returns exact metadata
  - metadata_type_filter: "integer columns" returns all integer columns
  - metadata_semantic_type: "email columns" returns columns with EMAIL type
  - metadata_entity_type: "customer tables" returns customer entity tables
  - metadata_relationship: "FK for orders" returns relationship edges

KG Traversal Tests:
  - kg_term_resolution: "revenue" resolves to sales.amount
  - kg_join_path_discovery: orders + customers + products returns 3-join path
  - kg_entity_hierarchy: "electronics" returns subcategory tables
  - kg_cross_db_traversal: Cross-database term resolution
  - kg_empty_graph: New tenant with no graph returns gracefully

Hybrid Ranking Tests:
  - rrf_fusion_basic: Combines 3 result sets correctly
  - rrf_fusion_weighted: Per-query-type weights applied
  - rrf_fusion_empty_set: One modality returns empty -> still fuses others
  - rrf_fusion_duplicates: Same document in multiple sets -> deduplication
  - rrf_score_normalization: Scores normalized before fusion

Reranking Tests:
  - rerank_improves_order: Cross-encoder fixes RRF order
  - rerank_low_confidence: All rerank scores < 0.5 -> fall back to RRF
  - rerank_batch_processing: 50 candidates processed in correct batch size
  - rerank_skip_conditions: Simple query correctly skips reranking

Expansion Tests:
  - expansion_synonym: "qty" -> ["quantity", "qty"]
  - expansion_business_term: "revenue" -> sales.amount columns
  - expansion_acronym: "sku" -> "stock_keeping_unit"
  - expansion_no_match: Unknown term returns original
  - expansion_deduplication: No duplicate tokens in expanded set

Context Compression Tests:
  - compression_fits: Context under token limit
  - compression_truncates: Context over limit -> truncated gracefully
  - compression_priority: High-priority components preserved
  - compression_empty: No context -> returns empty
  - compression_progressive: Progressive disclosure order correct

Cache Tests:
  - cache_hit_returns_cached: Same query returns cached result
  - cache_miss_retrieves_fresh: New query triggers full retrieval
  - cache_invalidation_schema: Schema change invalidates cache
  - cache_ttl_expiry: Expired cache triggers fresh retrieval
  - cache_tenant_isolation: Tenant keys don't collide

Resilience Tests:
  - qdrant_down_fallback: Qdrant unavailable -> keyword + metadata only
  - postgres_down_fallback: PostgreSQL unavailable -> vector + keyword only
  - reranker_down_fallback: Cross-encoder unavailable -> RRF only
  - embedder_down_fallback: Embedder unavailable -> use cached or skip
  - cache_down_fallback: Redis unavailable -> direct retrieval
  - all_down: All stores unavailable -> empty context gracefully
```

### 21.3 Test Data Requirements

| Dataset | Type | Tables | Columns | Purpose |
|---------|------|--------|---------|---------|
| Northwind | PostgreSQL | 13 | ~100 | Standard retrieval patterns |
| AdventureWorks | SQL Server | 70+ | ~800 | Complex schemas, cryptic names |
| TPC-H | PostgreSQL | 8 | ~60 | Analytical query patterns |
| Obscure naming | Custom | 50 | ~500 | t1, c1, cryptic names |
| Large schema | Custom | 5,000 | ~50,000 | Scale testing |
| Business ontology | Custom | - | ~500 terms | Ontology resolution |
| Cross-DB (PG + MySQL) | Mixed | 12 | ~200 | Cross-DB retrieval |
| Adversarial | Custom | 20 | ~200 | Misleading names, traps |

### 21.4 Acceptance Criteria

- [ ] All test scenarios pass in CI
- [ ] Recall@10 > 75% across all benchmarks
- [ ] Precision@10 > 65% across all benchmarks
- [ ] P50 retrieval latency < 250ms (all phases)
- [ ] P95 retrieval latency < 550ms (all phases)
- [ ] Graceful degradation for each component failure (verified by resilience tests)
- [ ] Tenant isolation verified (no cross-tenant leakage in any modality)
- [ ] Cache hit ratio > 40% in steady state (after warmup)
- [ ] Context compression never exceeds 8000 tokens

---

## 22. Future Improvements

### 22.1 Post-MVP Enhancements

| Enhancement | Value | Complexity | Timeline |
|-------------|-------|------------|----------|
| **Learned RRF weights** | +5-10% Recall@10 | Medium | Month 5 |
| **ColBERT late interaction** | +10-15% precision | High | Month 8 |
| **Multi-vector embeddings** | Better multi-faceted retrieval | High | Month 7 |
| **Query-aware embedding** | Embed query + context jointly | Medium | Month 6 |
| **Personalized retrieval** | Learn user-specific term preferences | Medium | Month 6 |
| **Active learning for reranker** | Improve reranker with user feedback | Medium | Month 5 |
| **Cross-encoder distillation** | Faster reranking with student model | Medium | Month 7 |
| **Hybrid index compression** | Reduce Qdrant memory 40% | Low | Month 3 |
| **Adaptive expansion depth** | Tune expansion based on query | Low | Month 4 |
| **Real-time index updates** | No delay for new schema elements | High | Month 9 |

### 22.2 Research Areas

| Area | Question | Approach |
|------|----------|---------|
| **Late interaction models** | Can ColBERT-style scoring improve precision without full cross-encoder? | Implement ColBERTv2, compare latency vs quality |
| **Graph-aware embeddings** | Can we encode graph structure into embeddings for better join discovery? | Graph neural network on Knowledge Graph |
| **Zero-shot domain adaptation** | Can retrieval generalize to unseen schema patterns? | Synthetic schema generation for pre-training |
| **Feedback-driven retriever** | Can negative user feedback improve future retrieval? | Online learning from implicit signals |

---

## Appendix A: Cross-References

| Retriever Component | Related Document | Relationship |
|---------------------|-----------------|--------------|
| Vector search | KnowledgeEngine-Specification.md \u00a78 | Embedding pipeline from KE |
| Keyword search | Schema-Specification.md \u00a710 | Synonym generation feeds keyword index |
| Metadata search | Database-Specification.md \u00a75 | Schema store tables used by metadata search |
| KG traversal | KnowledgeEngine-Specification.md \u00a75-\u00a76 | Knowledge graph stores business relationships |
| Business ontology | KnowledgeEngine-Specification.md \u00a76 | Business glossary in knowledge graph |
| Context output | AI-Agent-Specification.md \u00a73 | Retriever Agent consumes context |
| Reranking | Performance-Specification.md \u00a76 | Embedding latency + cost budgets |
| Cache strategy | Performance-Specification.md \u00a73 | Cache hierarchy design |
| Multi-tenant isolation | Security-Specification.md \u00a710 | Tenant isolation patterns |
| Retrieval API | API-Specification.md \u00a78.2 | Retriever API contracts |

## Appendix B: Design Decisions Log

| Decision | Option A | Option B | Winner | Rationale |
|----------|----------|----------|--------|-----------|
| Fusion method | Learned (LambdaRank) | RRF | RRF | Zero training data, interpretable, within 5% of learned |
| Reranker type | Cross-encoder | LLM-as-reranker | Cross-encoder | 10-50x faster, purpose-trained, no prompt engineering |
| Embedding model | BGE-M3 | OpenAI ada-002 | BGE-M3 | Self-hosted, hybrid (dense+sparse), no API cost, multilingual |
| Hybrid vector search | Weighted sum | Separate + RRF | Weighted sum | Dense and sparse scores are comparable (same system) |
| Context compression | LLM-based | Rule-based | Rule-based | Deterministic, fast, debuggable, no LLM cost |
| Expansion strategy | LLM-only | Synonym + LLM | Synonym + LLM | Cost efficient, LLM only when needed |

## Appendix C: Risks and Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| BGE-M3 quality insufficient for domain-specific schemas | Medium | High | Synonym-based fallback, domain fine-tuning path |
| Qdrant latency degrades at 1M+ vectors per tenant | Medium | Medium | Collection partitioning, HNSW tuning, read replicas |
| Cross-encoder latency exceeds budget | Medium | Medium | Skip reranking for simple queries, batch optimization |
| Keyword index stale after schema changes | Low | Medium | Real-time index updates, vector fallback |
| Cache invalidation misses schema change | Low | Low | Conservative TTL, version-based invalidation |

### Assumptions

| Assumption | Impact if Wrong | Validation |
|------------|----------------|------------|
| BGE-M3 provides adequate embedding quality for enterprise schema terms | Recall degrades 20%+ | Research spike EP-017 validates on enterprise datasets |
| RRF fusion within 5% of learned methods | Suboptimal ranking for 5% of queries | Benchmarked against LambdaRank on internal data |
| Cross-encoder reranker available with < 200ms P95 latency | Latency budget exceeded | Performance tested on MI300X |
| Cache hit ratio reaches 40%+ in steady state | Retrieval latency 50ms higher | Validated with production traffic simulation |
| Most queries (< 80%) can terminate after Phase 1 | Average latency 250ms instead of 150ms | Measured in production, early termination rules tuned |

## Appendix D: Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-10 | Principal Retrieval Architect | Initial specification \u2014 22 sections covering complete Hybrid Retrieval Engine |

---
*End of Retriever-Specification.md*
