import {
  useFetchKnowledgeBaseConfiguration,
  useFetchKnowledgeGraph,
} from '@/hooks/knowledge-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { Alert, Spin, Typography } from 'antd';
import { isEmpty } from 'lodash';
import React, { useEffect } from 'react';
import ForceGraph from './force-graph';

const KnowledgeGraphModal: React.FC = () => {
  const { data, loading } = useFetchKnowledgeGraph();
  const { data: knowledgeDetails } = useFetchKnowledgeBaseConfiguration();
  const { data: userInfo } = useFetchUserInfo();

  // 计算用户是否为知识库创建者
  const isCreator =
    userInfo?.id &&
    knowledgeDetails?.created_by &&
    userInfo.id === knowledgeDetails.created_by;

  useEffect(() => {
    console.log('Knowledge Graph Component - Data:', data);
    console.log('Knowledge Graph Component - Is Creator:', isCreator);
    console.log(
      'Knowledge Graph Component - Has Nodes:',
      data?.graph?.nodes?.length || 0,
    );
    console.log(
      'Knowledge Graph Component - Has Edges:',
      data?.graph?.edges?.length || 0,
    );
    console.log(
      'Knowledge Graph Component - Has Graph Data:',
      !isEmpty(data?.graph),
    );
  }, [data, isCreator]);

  if (loading) {
    return (
      <div className="flex items-center justify-center w-full h-full">
        <Spin tip="Loading knowledge graph..." />
      </div>
    );
  }

  if (
    !data ||
    isEmpty(data.graph) ||
    !data.graph.nodes ||
    data.graph.nodes.length === 0
  ) {
    return (
      <div className="flex flex-col items-center justify-center w-full h-full">
        <Alert
          type="info"
          message="No Knowledge Graph Available"
          description={
            <div>
              <Typography.Paragraph>
                There is no knowledge graph data available for this knowledge
                base.
              </Typography.Paragraph>
              <Typography.Paragraph>
                This might be because:
                <ul>
                  <li>The knowledge graph hasn't been generated yet</li>
                  <li>
                    There is not enough content to build a meaningful graph
                  </li>
                  <li>The knowledge graph extraction feature is not enabled</li>
                </ul>
              </Typography.Paragraph>
              {isCreator ? (
                <Typography.Paragraph>
                  As the creator of this knowledge base, you can enable
                  knowledge graph extraction in the configuration settings.
                </Typography.Paragraph>
              ) : (
                <Typography.Paragraph>
                  The knowledge graph may be generated later by the creator of
                  this knowledge base.
                </Typography.Paragraph>
              )}
            </div>
          }
          showIcon
        />
      </div>
    );
  }

  // 显示节点和边的数量信息
  console.log(
    `Rendering knowledge graph with ${data.graph.nodes.length} nodes and ${data.graph.edges?.length || 0} edges`,
  );

  return (
    <section className={'w-full h-full'}>
      <ForceGraph data={data?.graph} show></ForceGraph>
    </section>
  );
};

export default KnowledgeGraphModal;
