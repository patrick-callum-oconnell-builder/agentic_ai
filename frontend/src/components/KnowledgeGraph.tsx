import React, { useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface Node {
  id: string;
  type: string;
  attributes: Record<string, any>;
}

interface Link {
  source: string;
  target: string;
  type: string;
  attributes: Record<string, any>;
}

interface GraphData {
  nodes: Node[];
  links: Link[];
}

const KnowledgeGraph: React.FC = () => {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('http://localhost:8000/api/knowledge-graph')
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch knowledge graph');
        return res.json();
      })
      .then(raw => {
        // Convert backend dict to force-graph format
        const nodes = Object.entries(raw.entities).map(([id, v]: [string, any]) => ({
          id,
          ...v
        }));
        const links = Object.values(raw.relations).map((rel: any) => ({
          source: rel.source,
          target: rel.target,
          type: rel.type,
          attributes: rel.attributes
        }));
        setData({ nodes, links });
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div style={{ color: '#888', textAlign: 'center', width: '100%' }}>Loading knowledge graph...</div>;
  if (error) return <div style={{ color: 'red', textAlign: 'center', width: '100%' }}>Error: {error}</div>;

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ForceGraph2D
        graphData={data}
        nodeLabel={(node: Node) => `${node.id} (${node.type})`}
        linkLabel={(link: Link) => link.type}
        nodeAutoColorBy="type"
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        width={900}
        height={600}
      />
    </div>
  );
};

export default KnowledgeGraph; 