import { ResponseType } from '@/interfaces/database/base';
import { DSL, IFlow, IFlowTemplate } from '@/interfaces/database/flow';
import { IDebugSingleRequestBody } from '@/interfaces/request/flow';
import i18n from '@/locales/config';
import { useGetSharedChatSearchParams } from '@/pages/chat/shared-hooks';
import { BeginId } from '@/pages/flow/constant';
import flowService from '@/services/flow-service';
import { buildMessageListWithUuid } from '@/utils/chat';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { set } from 'lodash';
import get from 'lodash/get';
import { useParams } from 'umi';
import { v4 as uuid } from 'uuid';

export const EmptyDsl = {
  graph: {
    nodes: [
      {
        id: BeginId,
        type: 'beginNode',
        position: {
          x: 50,
          y: 200,
        },
        data: {
          label: 'Begin',
          name: 'begin',
        },
        sourcePosition: 'left',
        targetPosition: 'right',
      },
    ],
    edges: [],
  },
  components: {
    begin: {
      obj: {
        component_name: 'Begin',
        params: {},
      },
      downstream: ['Answer:China'], // other edge target is downstream, edge source is current node id
      upstream: [], // edge source is upstream, edge target is current node id
    },
  },
  messages: [],
  reference: [],
  history: [],
  path: [],
  answer: [],
};

export const useFetchFlowTemplates = (): ResponseType<IFlowTemplate[]> => {
  const { data } = useQuery({
    queryKey: ['fetchFlowTemplates'],
    initialData: [],
    queryFn: async () => {
      const { data } = await flowService.listTemplates();
      if (Array.isArray(data?.data)) {
        data.data.unshift({
          id: uuid(),
          title: 'Blank',
          description: 'Create your agent from scratch',
          dsl: EmptyDsl,
        });
      }

      return data;
    },
  });

  return data;
};

export const useFetchFlowList = (): { data: IFlow[]; loading: boolean } => {
  const { data, isFetching: loading } = useQuery({
    queryKey: ['fetchFlowList'],
    initialData: [],
    gcTime: 0,
    queryFn: async () => {
      const { data } = await flowService.listCanvas();

      return data?.data ?? [];
    },
  });

  return { data, loading };
};

export const useFetchFlow = (): {
  data: IFlow;
  loading: boolean;
  refetch: () => void;
} => {
  const { id } = useParams();
  const { sharedId } = useGetSharedChatSearchParams();

  const {
    data,
    isFetching: loading,
    refetch,
  } = useQuery({
    queryKey: ['flowDetail'],
    initialData: {} as IFlow,
    refetchOnReconnect: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    gcTime: 0,
    queryFn: async () => {
      const { data } = await flowService.getCanvas({}, sharedId || id);

      const messageList = buildMessageListWithUuid(
        get(data, 'data.dsl.messages', []),
      );
      set(data, 'data.dsl.messages', messageList);

      return data?.data ?? {};
    },
  });

  return { data, loading, refetch };
};

export const useFetchFlowSSE = (): {
  data: IFlow;
  loading: boolean;
  refetch: () => void;
} => {
  const { sharedId } = useGetSharedChatSearchParams();

  const {
    data,
    isFetching: loading,
    refetch,
  } = useQuery({
    queryKey: ['flowDetailSSE'],
    initialData: {} as IFlow,
    refetchOnReconnect: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    gcTime: 0,
    queryFn: async () => {
      if (!sharedId) return {};
      const { data } = await flowService.getCanvasSSE({}, sharedId);

      const messageList = buildMessageListWithUuid(
        get(data, 'data.dsl.messages', []),
      );
      set(data, 'data.dsl.messages', messageList);

      return data?.data ?? {};
    },
  });

  return { data, loading, refetch };
};

export const useSetFlow = () => {
  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['setFlow'],
    mutationFn: async (params: {
      id?: string;
      title?: string;
      dsl?: DSL;
      avatar?: string;
    }) => {
      const { data = {} } = await flowService.setCanvas(params);
      if (data.code === 0) {
        message.success(
          i18n.t(`message.${params?.id ? 'modified' : 'created'}`),
        );
        queryClient.invalidateQueries({ queryKey: ['fetchFlowList'] });
      }
      return data;
    },
  });

  return { data, loading, setFlow: mutateAsync };
};

export const useDeleteFlow = () => {
  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['deleteFlow'],
    mutationFn: async (canvasIds: string[]) => {
      const { data } = await flowService.removeCanvas({ canvasIds });
      if (data.code === 0) {
        queryClient.invalidateQueries({ queryKey: ['fetchFlowList'] });
      }
      return data?.data ?? [];
    },
  });

  return { data, loading, deleteFlow: mutateAsync };
};

export const useRunFlow = () => {
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['runFlow'],
    mutationFn: async (params: { id: string; dsl: DSL }) => {
      const { data } = await flowService.runCanvas(params);
      if (data.code === 0) {
        message.success(i18n.t(`message.modified`));
      }
      return data?.data ?? {};
    },
  });

  return { data, loading, runFlow: mutateAsync };
};

export const useResetFlow = () => {
  const { id } = useParams();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['resetFlow'],
    mutationFn: async () => {
      const { data } = await flowService.resetCanvas({ id });
      return data;
    },
  });

  return { data, loading, resetFlow: mutateAsync };
};

export const useTestDbConnect = () => {
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['testDbConnect'],
    mutationFn: async (params: any) => {
      const ret = await flowService.testDbConnect(params);
      if (ret?.data?.code !== 0 && ret?.data?.code !== 200) {
        message.error(ret?.data?.data);
      }
      return ret;
    },
  });

  return { data, loading, testDbConnect: mutateAsync };
};

export const useFetchInputElements = (componentId?: string) => {
  const { id } = useParams();

  const { data, isPending: loading } = useQuery({
    queryKey: ['fetchInputElements', id, componentId],
    initialData: [],
    enabled: !!id && !!componentId,
    retryOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    gcTime: 0,
    queryFn: async () => {
      try {
        const { data } = await flowService.getInputElements({
          id,
          component_id: componentId,
        });
        return data?.data ?? [];
      } catch (error) {
        console.log('🚀 ~ queryFn: ~ error:', error);
      }
    },
  });

  return { data, loading };
};

export const useDebugSingle = () => {
  const { id } = useParams();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['debugSingle'],
    mutationFn: async (params: IDebugSingleRequestBody) => {
      const ret = await flowService.debugSingle({ id, ...params });
      if (ret?.data?.code !== 0 && ret?.data?.code !== 200) {
        message.error(ret?.data?.message);
      }
      return ret?.data?.data;
    },
  });

  return { data, loading, debugSingle: mutateAsync };
};

// Agent信息类型
export interface AgentInfo {
  permission: 'private' | 'team' | 'public';
  tags: string[];
  canvas_industry?: string;
  team_ids?: string[];
  user_id?: string;
  is_recommended?: boolean;
}

// 默认值
const DEFAULT_AGENT_INFO: AgentInfo = {
  permission: 'private',
  tags: [],
  canvas_industry: '',
  team_ids: [],
  user_id: '',
  is_recommended: false,
} as const;

// 权限映射
const PERMISSION_MAP: Record<string, AgentInfo['permission']> = {
  private: 'private',
  team: 'team',
  public: 'public',
} as const;

// 获取Agent信息
export const useFetchAgentInfo = (agentId: string) => {
  const {
    data,
    isFetching: loading,
    refetch,
  } = useQuery({
    queryKey: ['agentInfo', agentId],
    enabled: !!agentId,
    retry: 0,
    staleTime: 30000, // 数据30秒内认为是新鲜的
    queryFn: async () => {
      try {
        const response = await flowService.getAgentInfo({ canvas_id: agentId });
        const apiData = response?.data?.data;

        if (!apiData) {
          return DEFAULT_AGENT_INFO;
        }

        // 确保权限值有效
        const permission =
          PERMISSION_MAP[apiData.canvas_permissions] ||
          DEFAULT_AGENT_INFO.permission;

        // 确保标签是数组
        const tags = Array.isArray(apiData.canvas_tag)
          ? apiData.canvas_tag
          : DEFAULT_AGENT_INFO.tags;

        // 获取行业信息
        const canvas_industry =
          apiData.canvas_industry || DEFAULT_AGENT_INFO.canvas_industry;

        // 获取团队ID列表
        const team_ids = apiData.team_ids || DEFAULT_AGENT_INFO.team_ids;

        // 获取推荐状态
        const is_recommended =
          typeof apiData.is_recommended === 'boolean'
            ? apiData.is_recommended
            : DEFAULT_AGENT_INFO.is_recommended;

        return {
          permission,
          tags,
          canvas_industry,
          team_ids,
          user_id: apiData.user_id || DEFAULT_AGENT_INFO.user_id,
          is_recommended,
        };
      } catch (error) {
        console.error('Failed to fetch agent info:', error);
        return DEFAULT_AGENT_INFO;
      }
    },
  });

  // 使用默认值作为后备
  return {
    data: data || DEFAULT_AGENT_INFO,
    loading,
    refetch,
  };
};

// 更新Agent信息
export const useUpdateAgentInfo = () => {
  const queryClient = useQueryClient();

  const { mutateAsync, isPending: loading } = useMutation({
    mutationKey: ['updateAgentInfo'],
    mutationFn: async (params: {
      canvas_id: string;
      canvas_tag: string[];
      canvas_permissions: 'private' | 'team' | 'public';
      canvas_industry?: string;
      team_ids?: string[];
      is_recommended?: boolean;
    }) => {
      const { data } = await flowService.setAgentInfo(params);

      if (data.code === 0) {
        // 更新缓存
        queryClient.invalidateQueries({
          queryKey: ['agentInfo', params.canvas_id],
        });
      }

      return data;
    },
  });

  return {
    updateAgentInfo: mutateAsync,
    loading,
  };
};
