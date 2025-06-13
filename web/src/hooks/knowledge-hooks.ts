import { ResponsePostType } from '@/interfaces/database/base';
import {
  IKnowledge,
  IKnowledgeGraph,
  IRenameTag,
  ITestingResult,
} from '@/interfaces/database/knowledge';
import i18n from '@/locales/config';
import kbService, {
  getKnowledgeGraph,
  listTag,
  removeTag,
  renameTag,
} from '@/services/knowledge-service';
import {
  useInfiniteQuery,
  useIsMutating,
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useDebounce } from 'ahooks';
import { message } from 'antd';
import { isEmpty } from 'lodash';
import { useState } from 'react';
import { useSearchParams } from 'umi';
import { useHandleSearchChange } from './logic-hooks';
import { useSetPaginationParams } from './route-hook';

export const useKnowledgeBaseId = (): string => {
  const [searchParams] = useSearchParams();
  const knowledgeBaseId = searchParams.get('id');

  return knowledgeBaseId || '';
};

export const useFetchKnowledgeBaseConfiguration = () => {
  const knowledgeBaseId = useKnowledgeBaseId();

  const {
    data,
    isFetching: loading,
    error,
  } = useQuery<IKnowledge>({
    queryKey: ['fetchKnowledgeDetail'],
    initialData: {} as IKnowledge,
    gcTime: 0,
    queryFn: async () => {
      if (!knowledgeBaseId) {
        return {} as IKnowledge;
      }

      try {
        const response = await kbService.get_kb_detail({
          kb_id: knowledgeBaseId,
        });

        // If the response has an error code but it's related to permissions, just return empty data
        if (response.data?.code === 109) {
          console.log('KB access permission error, returning empty data');
          return {} as IKnowledge;
        }

        if (!response.data?.data) {
          return {} as IKnowledge;
        }

        return response.data.data;
      } catch (error) {
        console.error('Error fetching knowledge details:', error);
        // Always return empty data instead of throwing error
        return {} as IKnowledge;
      }
    },
  });

  return { data, loading, error };
};

export const useFetchKnowledgeList = (
  shouldFilterListWithoutDocument: boolean = false,
): {
  list: IKnowledge[];
  loading: boolean;
} => {
  const { data, isFetching: loading } = useQuery({
    queryKey: ['fetchKnowledgeList'],
    initialData: [],
    gcTime: 0, // https://tanstack.com/query/latest/docs/framework/react/guides/caching?from=reactQueryV3
    queryFn: async () => {
      const { data } = await kbService.getList();
      const list = data?.data?.kbs ?? [];
      return shouldFilterListWithoutDocument
        ? list.filter((x: IKnowledge) => x.chunk_num > 0)
        : list;
    },
  });

  return { list: data, loading };
};

export const useSelectKnowledgeOptions = () => {
  const { list } = useFetchKnowledgeList();

  const options = list?.map((item) => ({
    label: item.name,
    value: item.id,
  }));

  return options;
};

export const useInfiniteFetchKnowledgeList = () => {
  const { searchString, handleInputChange } = useHandleSearchChange();
  const debouncedSearchString = useDebounce(searchString, { wait: 500 });

  const PageSize = 30;
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
  } = useInfiniteQuery({
    queryKey: ['infiniteFetchKnowledgeList', debouncedSearchString],
    queryFn: async ({ pageParam }) => {
      const { data } = await kbService.getList({
        page: pageParam,
        page_size: PageSize,
        keywords: debouncedSearchString,
      });
      const list = data?.data ?? [];
      return list;
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage, pages, lastPageParam) => {
      if (lastPageParam * PageSize <= lastPage.total) {
        return lastPageParam + 1;
      }
      return undefined;
    },
  });
  return {
    data,
    loading: isFetching,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    status,
    handleInputChange,
    searchString,
  };
};

export const useCreateKnowledge = () => {
  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['createKnowledge'],
    mutationFn: async (params: { id?: string; name: string }) => {
      const { data = {} } = await kbService.createKb(params);
      if (data.code === 0) {
        message.success(
          i18n.t(`message.${params?.id ? 'modified' : 'created'}`),
        );
        queryClient.invalidateQueries({ queryKey: ['fetchKnowledgeList'] });
      }
      return data;
    },
  });

  return { data, loading, createKnowledge: mutateAsync };
};

export const useDeleteKnowledge = () => {
  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['deleteKnowledge'],
    mutationFn: async (id: string) => {
      try {
        const { data } = await kbService.rmKb({ kb_id: id });
        // 仅在成功时显示成功消息
        if (data.code === 0) {
          message.success(i18n.t(`message.deleted`));
          queryClient.invalidateQueries({
            queryKey: ['infiniteFetchKnowledgeList'],
          });
        } else if (data.code === 109) {
          // 对于权限错误，显示明确的权限错误消息
          message.error(
            i18n.t('message.noPermissionToDelete') || '您没有权限删除此知识库',
          );
        }
        return data?.data ?? [];
      } catch (error) {
        // 确保捕获和处理所有可能的错误
        console.error('Failed to delete knowledge base:', error);
        message.error(i18n.t('message.deleteFailed') || '删除失败');
        throw error;
      }
    },
  });

  return { data, loading, deleteKnowledge: mutateAsync };
};

//#region knowledge configuration

export const useUpdateKnowledge = () => {
  const knowledgeBaseId = useKnowledgeBaseId();
  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['saveKnowledge'],
    mutationFn: async (params: Record<string, any>) => {
      const { data = {} } = await kbService.updateKb({
        kb_id: knowledgeBaseId,
        ...params,
      });
      if (data.code === 0) {
        message.success(i18n.t(`message.updated`));
        queryClient.invalidateQueries({ queryKey: ['fetchKnowledgeDetail'] });
      }
      return data;
    },
  });

  return { data, loading, saveKnowledgeConfiguration: mutateAsync };
};

//#endregion

//#region Retrieval testing

export const useTestChunkRetrieval = (): ResponsePostType<ITestingResult> & {
  testChunk: (...params: any[]) => void;
} => {
  const knowledgeBaseId = useKnowledgeBaseId();
  const { page, size: pageSize } = useSetPaginationParams();

  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['testChunk'], // This method is invalid
    gcTime: 0,
    mutationFn: async (values: any) => {
      const { data } = await kbService.retrieval_test({
        ...values,
        kb_id: values.kb_id ?? knowledgeBaseId,
        page,
        size: pageSize,
      });
      if (data.code === 0) {
        const res = data.data;
        return {
          ...res,
          documents: res.doc_aggs,
        };
      }
      return (
        data?.data ?? {
          chunks: [],
          documents: [],
          total: 0,
        }
      );
    },
  });

  return {
    data: data ?? { chunks: [], documents: [], total: 0 },
    loading,
    testChunk: mutateAsync,
  };
};

export const useChunkIsTesting = () => {
  return useIsMutating({ mutationKey: ['testChunk'] }) > 0;
};

export const useSelectTestingResult = (): ITestingResult => {
  const data = useMutationState({
    filters: { mutationKey: ['testChunk'] },
    select: (mutation) => {
      return mutation.state.data;
    },
  });
  return (data.at(-1) ?? {
    chunks: [],
    documents: [],
    total: 0,
  }) as ITestingResult;
};

export const useSelectIsTestingSuccess = () => {
  const status = useMutationState({
    filters: { mutationKey: ['testChunk'] },
    select: (mutation) => {
      return mutation.state.status;
    },
  });
  return status.at(-1) === 'success';
};
//#endregion

//#region tags

export const useFetchTagList = () => {
  const knowledgeBaseId = useKnowledgeBaseId();

  const { data, isFetching: loading } = useQuery<Array<[string, number]>>({
    queryKey: ['fetchTagList'],
    initialData: [],
    gcTime: 0, // https://tanstack.com/query/latest/docs/framework/react/guides/caching?from=reactQueryV3
    queryFn: async () => {
      const { data } = await listTag(knowledgeBaseId);
      const list = data?.data || [];
      return list;
    },
  });

  return { list: data, loading };
};

export const useDeleteTag = () => {
  const knowledgeBaseId = useKnowledgeBaseId();

  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['deleteTag'],
    mutationFn: async (tags: string[]) => {
      const { data } = await removeTag(knowledgeBaseId, tags);
      if (data.code === 0) {
        message.success(i18n.t(`message.deleted`));
        queryClient.invalidateQueries({
          queryKey: ['fetchTagList'],
        });
      }
      return data?.data ?? [];
    },
  });

  return { data, loading, deleteTag: mutateAsync };
};

export const useRenameTag = () => {
  const knowledgeBaseId = useKnowledgeBaseId();

  const queryClient = useQueryClient();
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['renameTag'],
    mutationFn: async (params: IRenameTag) => {
      const { data } = await renameTag(knowledgeBaseId, params);
      if (data.code === 0) {
        message.success(i18n.t(`message.modified`));
        queryClient.invalidateQueries({
          queryKey: ['fetchTagList'],
        });
      }
      return data?.data ?? [];
    },
  });

  return { data, loading, renameTag: mutateAsync };
};

export const useTagIsRenaming = () => {
  return useIsMutating({ mutationKey: ['renameTag'] }) > 0;
};

export const useFetchTagListByKnowledgeIds = () => {
  const [knowledgeIds, setKnowledgeIds] = useState<string[]>([]);

  const { data, isFetching: loading } = useQuery<Array<[string, number]>>({
    queryKey: ['fetchTagListByKnowledgeIds'],
    enabled: knowledgeIds.length > 0,
    initialData: [],
    gcTime: 0, // https://tanstack.com/query/latest/docs/framework/react/guides/caching?from=reactQueryV3
    queryFn: async () => {
      const { data } = await kbService.listTagByKnowledgeIds({
        kb_ids: knowledgeIds.join(','),
      });
      const list = data?.data || [];
      return list;
    },
  });

  return { list: data, loading, setKnowledgeIds };
};

//#endregion

export function useFetchKnowledgeGraph() {
  const knowledgeBaseId = useKnowledgeBaseId();

  const { data, isFetching: loading } = useQuery<IKnowledgeGraph>({
    queryKey: ['fetchKnowledgeGraph', knowledgeBaseId],
    initialData: { graph: {}, mind_map: {} } as IKnowledgeGraph,
    enabled: !!knowledgeBaseId,
    gcTime: 0,
    queryFn: async () => {
      try {
        console.log(
          'Fetching knowledge graph for knowledgeBaseId:',
          knowledgeBaseId,
        );
        const response = await getKnowledgeGraph(knowledgeBaseId);
        console.log('Knowledge graph API complete response:', response);

        // 检查HTTP响应状态
        if (!response || !response.data) {
          console.log('Knowledge graph API returned empty response');
          return { graph: {}, mind_map: {} } as IKnowledgeGraph;
        }

        // 处理可能的API错误码
        if (response.data?.code !== 0) {
          console.log(
            `KB graph API returned error code ${response.data?.code}, message: ${response.data?.message || 'No message'}`,
          );
          return { graph: {}, mind_map: {} } as IKnowledgeGraph;
        }

        console.log(
          'Knowledge graph data structure:',
          Object.keys(response.data?.data || {}),
        );
        console.log(
          'Knowledge graph nodes:',
          response.data?.data?.graph?.nodes?.length || 0,
        );
        console.log(
          'Knowledge graph edges:',
          response.data?.data?.graph?.edges?.length || 0,
        );
        console.log(
          'Knowledge graph has data:',
          !isEmpty(response.data?.data?.graph),
        );

        // 确保返回有效的数据结构，即使API返回空数据
        const graphData = response.data?.data || { graph: {}, mind_map: {} };

        // 如果图数据为空，尝试提供有用的调试信息
        if (isEmpty(graphData.graph)) {
          console.log(
            'Knowledge graph data is empty, this may be normal for knowledge bases without graph data',
          );
        }

        return graphData;
      } catch (error) {
        console.error('Error fetching knowledge graph:', error);
        // Return empty data instead of throwing error
        return { graph: {}, mind_map: {} } as IKnowledgeGraph;
      }
    },
  });

  // 记录查询结果的状态
  console.log('useFetchKnowledgeGraph hook - Data available:', !!data);
  console.log(
    'useFetchKnowledgeGraph hook - Graph has nodes:',
    data?.graph?.nodes?.length || 0,
  );
  console.log('useFetchKnowledgeGraph hook - Loading:', loading);

  return { data, loading };
}
