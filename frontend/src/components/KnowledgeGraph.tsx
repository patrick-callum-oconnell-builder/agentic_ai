import React, { useEffect, useState, useRef } from 'react';
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
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 400 });
  const fgRef = useRef<any>(null);

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

  useEffect(() => {
    function updateSize() {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight
        });
      }
    }
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  useEffect(() => {
    if (fgRef.current) {
      fgRef.current.d3Force('link')?.distance(120);
    }
  }, [dimensions, data]);

  if (loading) return <div style={{ color: '#888', textAlign: 'center', width: '100%' }}>Loading knowledge graph...</div>;
  if (error) return <div style={{ color: 'red', textAlign: 'center', width: '100%' }}>Error: {error}</div>;

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }}>
      <ForceGraph2D
        ref={fgRef}
        graphData={data}
        nodeLabel={(node: Node) => `${node.id} (${node.type})`}
        linkLabel={(link: Link) => link.type}
        nodeAutoColorBy="type"
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        nodeRelSize={12}
        width={dimensions.width}
        height={dimensions.height}
        nodeCanvasObjectMode={() => 'after'}
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          ctx.font = `${16/globalScale}px Sans-Serif`;
          ctx.fillStyle = '#222';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(node.id, (node.x ?? 0), (node.y ?? 0) + 18);
        }}
      />
    </div>
  );
};

export default KnowledgeGraph; 