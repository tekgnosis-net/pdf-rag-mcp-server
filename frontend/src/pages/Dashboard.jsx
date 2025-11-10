import React, { useCallback, useEffect, useMemo, useState } from 'react';  
import {
  Box,
  Badge,
  Button,
  Divider,
  Flex,
  Heading,
  SimpleGrid,
  Stack,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
  Text,
  useToast,
} from '@chakra-ui/react';  
import axios from 'axios';  
import FileUpload from '../components/FileUpload';  
import FileList from '../components/FileList';  
import { useWebSocket } from '../context/WebSocketContext';  

const Dashboard = () => {  
  const [documents, setDocuments] = useState([]);  
  const [showAllProcessing, setShowAllProcessing] = useState(false);
  const [showAllProcessed, setShowAllProcessed] = useState(false);
  const {
    processingStatus,
    isConnected,
    connectionSnapshot,
    refreshConnectionSnapshot,
  } = useWebSocket();  
  const toast = useToast();  
  
  const websocketClients = connectionSnapshot?.websocketClients ?? [];
  const mcpSessions = connectionSnapshot?.mcpSessions ?? [];
  const snapshotGeneratedAt = connectionSnapshot?.generatedAt ?? null;
  
  const formatStatusLabel = useCallback((status) => {
    if (typeof status !== 'string' || status.length === 0) {
      return 'Unknown';
    }
    return status.charAt(0).toUpperCase() + status.slice(1);
  }, []);
  
  const statusColorScheme = useCallback((status) => {
    if (!status) {
      return 'gray';
    }
    const normalized = status.toLowerCase();
    if (normalized === 'connected') {
      return 'green';
    }
    if (normalized === 'disconnected') {
      return 'red';
    }
    if (normalized === 'error') {
      return 'orange';
    }
    return 'gray';
  }, []);
  
  const formatTimestamp = useCallback((value) => {
    if (!value) {
      return '—';
    }
    const timestamp = new Date(value);
    if (Number.isNaN(timestamp.getTime())) {
      return '—';
    }
    return timestamp.toLocaleString();
  }, []);
  
  const formatClientAddress = useCallback((clientHost, clientPort) => {
    if (!clientHost && !clientPort) {
      return 'Unknown client';
    }
    return clientPort ? `${clientHost ?? 'Unknown'}:${clientPort}` : (clientHost ?? 'Unknown client');
  }, []);
  
  const sortedWebsocketClients = useMemo(() => {
    const entries = Array.isArray(websocketClients) ? [...websocketClients] : [];
    entries.sort((a, b) => {
      const aConnected = (a?.status ?? '').toLowerCase() === 'connected';
      const bConnected = (b?.status ?? '').toLowerCase() === 'connected';
      if (aConnected !== bConnected) {
        return aConnected ? -1 : 1;
      }
      const aTime = a?.connected_at ? new Date(a.connected_at).getTime() : 0;
      const bTime = b?.connected_at ? new Date(b.connected_at).getTime() : 0;
      return bTime - aTime;
    });
    return entries;
  }, [websocketClients]);
  
  const sortedMcpSessions = useMemo(() => {
    const entries = Array.isArray(mcpSessions) ? [...mcpSessions] : [];
    entries.sort((a, b) => {
      const aConnected = (a?.status ?? '').toLowerCase() === 'connected';
      const bConnected = (b?.status ?? '').toLowerCase() === 'connected';
      if (aConnected !== bConnected) {
        return aConnected ? -1 : 1;
      }
      const aTime = a?.connected_at ? new Date(a.connected_at).getTime() : 0;
      const bTime = b?.connected_at ? new Date(b.connected_at).getTime() : 0;
      return bTime - aTime;
    });
    return entries;
  }, [mcpSessions]);

  const fetchDocuments = useCallback(async () => {  
    try {  
      const response = await axios.get('/api/documents');  
      setDocuments(response.data);  
    } catch (error) {  
      console.error("Failed to fetch documents:", error);  
      toast({  
        title: "Error",  
        description: "Failed to fetch documents",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    }  
  }, [toast]);  

  useEffect(() => {  
    fetchDocuments();  
    // Set up refresh interval  
    const intervalId = setInterval(fetchDocuments, 15000);  
    return () => clearInterval(intervalId);  
  }, [fetchDocuments]);  

  // Merge document status with WebSocket status  
  const enhancedDocuments = useMemo(() => (
    documents.map((doc) => {
      const statusKey = doc?.filename || doc?.file_path || doc?.id;
      const wsStatus = statusKey ? processingStatus[statusKey] : undefined;
      const wsProgress = wsStatus && typeof wsStatus.progress === 'number' ? wsStatus.progress : undefined;
      const statusFromWs = wsStatus?.status;
      const pageCurrent = typeof wsStatus?.page_current === 'number' ? wsStatus.page_current : null;
      const pageTotal = typeof wsStatus?.page_total === 'number' ? wsStatus.page_total : null;

      let statusText = statusFromWs || (doc.processed ? 'Completed' : doc.processing ? 'Processing' : 'Queued');
      if (doc.error) {
        statusText = doc.error.startsWith('Error') ? doc.error : `Error: ${doc.error}`;
      }

      const dbProgress = typeof doc.progress === 'number' ? doc.progress : 0;
      let effectiveProgress = typeof wsProgress === 'number' ? wsProgress : dbProgress;

      if (statusFromWs) {
        const normalizedStatus = statusFromWs.toLowerCase();
        if (normalizedStatus.includes('completed')) {
          effectiveProgress = 100;
        } else if (normalizedStatus.includes('storing in vector database')) {
          effectiveProgress = Math.max(effectiveProgress, 75);
        } else if (normalizedStatus.includes('generating embeddings')) {
          effectiveProgress = Math.max(effectiveProgress, 70);
        } else if (normalizedStatus.includes('running ocr') && pageTotal && pageTotal > 0) {
          const ratio = Math.min(Math.max((pageCurrent || 0) / pageTotal, 0), 1);
          effectiveProgress = Math.max(effectiveProgress, 50 + ratio * 20);
        } else if (normalizedStatus.includes('parsing pdf') && pageTotal && pageTotal > 0) {
          const ratio = Math.min(Math.max((pageCurrent || 0) / pageTotal, 0), 1);
          effectiveProgress = Math.max(effectiveProgress, ratio * 50);
        }
      }

      if (!statusFromWs && doc.processing && !doc.processed) {
        effectiveProgress = Math.max(effectiveProgress, 1);
      }

      const clampedProgress = Number.isFinite(effectiveProgress)
        ? Math.max(0, Math.min(100, effectiveProgress))
        : 0;

      return {
        ...doc,
        wsStatus,
        progress: clampedProgress,
        statusText,
        pageCurrent,
        pageTotal,
      };
    })
  ), [documents, processingStatus]);

  const processingDocs = useMemo(
    () => enhancedDocuments.filter((doc) => !doc.processed),
    [enhancedDocuments],
  );

  const processedDocs = useMemo(
    () => enhancedDocuments.filter((doc) => doc.processed),
    [enhancedDocuments],
  );

  const sortedProcessingDocs = useMemo(() => {
    const docsCopy = [...processingDocs];
    docsCopy.sort((a, b) => {
      const progressDiff = (b.progress ?? 0) - (a.progress ?? 0);
      if (progressDiff !== 0) {
        return progressDiff;
      }
      const aDate = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0;
      const bDate = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0;
      return bDate - aDate;
    });
    return docsCopy;
  }, [processingDocs]);

  const sortedProcessedDocs = useMemo(() => {
    const docsCopy = [...processedDocs];
    docsCopy.sort((a, b) => {
      const aDate = a.uploaded_at ? new Date(a.uploaded_at).getTime() : 0;
      const bDate = b.uploaded_at ? new Date(b.uploaded_at).getTime() : 0;
      return bDate - aDate;
    });
    return docsCopy;
  }, [processedDocs]);

  const processingDisplayLimit = 100;
  const hasMoreProcessing = sortedProcessingDocs.length > processingDisplayLimit;
  const displayedProcessingDocs = useMemo(
    () => (showAllProcessing ? sortedProcessingDocs : sortedProcessingDocs.slice(0, processingDisplayLimit)),
    [showAllProcessing, sortedProcessingDocs],
  );

  const processedDisplayLimit = 200;
  const hasMoreProcessed = sortedProcessedDocs.length > processedDisplayLimit;
  const displayedProcessedDocs = useMemo(
    () => (showAllProcessed ? sortedProcessedDocs : sortedProcessedDocs.slice(0, processedDisplayLimit)),
    [showAllProcessed, sortedProcessedDocs],
  );

  const handleFileUploaded = () => {  
    // Refresh document list  
    fetchDocuments();  
  };  

  return (
    <Stack spacing={{ base: 6, lg: 8 }}>
      <Stack spacing={2}>
        <Heading as="h1" size={{ base: 'lg', md: 'xl' }}>MCP PDF Knowledge Base</Heading>
        <Text color="gray.600" fontSize={{ base: 'sm', md: 'md' }}>
          Upload documents, monitor ingestion, and manage your MCP connection in one place.
        </Text>
      </Stack>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
          <Heading as="h2" size="md" mb={3}>
            Upload New PDF
          </Heading>
          <Text fontSize="sm" color="gray.600" mb={4}>
            PDFs are processed into searchable chunks and made available to MCP clients.
          </Text>
          <FileUpload onFileUploaded={handleFileUploaded} />
        </Box>

        <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
          <Flex justify="space-between" align={{ base: 'flex-start', md: 'center' }} gap={3} mb={3} direction={{ base: 'column', md: 'row' }}>
            <Box>
              <Heading as="h2" size="md" mb={1}>
                Client Connections
              </Heading>
              <Text fontSize="sm" color="gray.600">
                Monitor live dashboard sockets and MCP clients in one view.
              </Text>
            </Box>
            <Button size="sm" variant="outline" onClick={refreshConnectionSnapshot}>
              Refresh
            </Button>
          </Flex>

          <Stack spacing={3}>
            <Flex align="center" gap={3}>
              <Text fontWeight="semibold" fontSize="sm">
                Dashboard socket
              </Text>
              <Badge colorScheme={isConnected ? 'green' : 'red'}>
                {isConnected ? 'Connected' : 'Disconnected'}
              </Badge>
            </Flex>

            {snapshotGeneratedAt && (
              <Text fontSize="xs" color="gray.500">
                Last update: {formatTimestamp(snapshotGeneratedAt)}
              </Text>
            )}

            <Divider />

            <Box>
              <Flex justify="space-between" align="center">
                <Text fontWeight="semibold" fontSize="sm">
                  Web dashboard clients
                </Text>
                <Badge colorScheme={sortedWebsocketClients.length ? 'blue' : 'gray'}>
                  {sortedWebsocketClients.length}
                </Badge>
              </Flex>
              <Box mt={2} maxH="180px" overflowY="auto">
                {sortedWebsocketClients.length ? (
                  <Stack spacing={2}>
                    {sortedWebsocketClients.map((client) => (
                      <Box key={client.connection_id ?? `${client.client_host}-${client.client_port}`} borderWidth="1px" borderColor="gray.100" borderRadius="md" p={3}>
                        <Flex justify="space-between" align="baseline" mb={1}>
                          <Text fontWeight="medium" fontSize="sm">
                            {formatClientAddress(client.client_host, client.client_port)}
                          </Text>
                          <Badge colorScheme={statusColorScheme(client.status)}>
                            {formatStatusLabel(client.status)}
                          </Badge>
                        </Flex>
                        <Text fontSize="xs" color="gray.600">
                          Path: {client.path || '—'}
                        </Text>
                        <Text fontSize="xs" color="gray.600">
                          Connected: {formatTimestamp(client.connected_at)}
                        </Text>
                      </Box>
                    ))}
                  </Stack>
                ) : (
                  <Text fontSize="sm" color="gray.500">
                    No active dashboard clients
                  </Text>
                )}
              </Box>
            </Box>

            <Divider />

            <Box>
              <Flex justify="space-between" align="center">
                <Text fontWeight="semibold" fontSize="sm">
                  MCP clients
                </Text>
                <Badge colorScheme={sortedMcpSessions.length ? 'purple' : 'gray'}>
                  {sortedMcpSessions.filter((session) => (session?.status ?? '').toLowerCase() === 'connected').length}
                  {sortedMcpSessions.length > 0 ? ` / ${sortedMcpSessions.length}` : ''}
                </Badge>
              </Flex>
              <Box mt={2} maxH="180px" overflowY="auto">
                {sortedMcpSessions.length ? (
                  <Stack spacing={2}>
                    {sortedMcpSessions.map((session) => (
                      <Box key={session.session_id} borderWidth="1px" borderColor="gray.100" borderRadius="md" p={3}>
                        <Flex justify="space-between" align="baseline" mb={1}>
                          <Text fontWeight="medium" fontSize="sm">
                            {formatClientAddress(session.client_host, session.client_port)}
                          </Text>
                          <Badge colorScheme={statusColorScheme(session.status)}>
                            {formatStatusLabel(session.status)}
                          </Badge>
                        </Flex>
                        <Text fontSize="xs" color="gray.600">
                          Session: {session.session_uuid?.slice(0, 8) ?? session.session_id?.slice(0, 8) ?? '—'}
                        </Text>
                        <Text fontSize="xs" color="gray.600">
                          Connected: {formatTimestamp(session.connected_at)}
                        </Text>
                        <Text fontSize="xs" color="gray.600">
                          Last activity: {formatTimestamp(session.last_message_at || session.disconnected_at || session.connected_at)}
                        </Text>
                        <Text fontSize="xs" color="gray.600">
                          Messages received: {session.messages_received ?? 0}
                        </Text>
                      </Box>
                    ))}
                  </Stack>
                ) : (
                  <Text fontSize="sm" color="gray.500">
                    No MCP clients connected yet
                  </Text>
                )}
              </Box>
            </Box>

            <Divider />

            <Text fontSize="xs" color="gray.600">
              Configure in your AI/LLM chat client: Settings → MCP Servers → Add URL: http://MCP-SERVER-IP:DOCKER_PORT/mcp
            </Text>
          </Stack>
        </Box>
      </SimpleGrid>

      <Box bg="white" p={{ base: 5, md: 6 }} shadow="md" borderRadius="lg">
        <Heading as="h2" size="md" mb={4}>
          Your Documents
        </Heading>

        <Tabs variant="soft-rounded" colorScheme="blue" isFitted>
          <TabList>
            <Tab>Processing ({sortedProcessingDocs.length})</Tab>  
            <Tab>Completed ({sortedProcessedDocs.length})</Tab>  
          </TabList>

          <TabPanels>
            <TabPanel px={{ base: 0, md: 2 }}>
              {sortedProcessingDocs.length > 0 ? (
                <Stack spacing={4}>
                  <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" gap={3}>
                    <Text color="gray.600" fontSize="sm">
                      Showing {displayedProcessingDocs.length} of {sortedProcessingDocs.length} processing documents.
                    </Text>
                    {hasMoreProcessing && (
                      <Button size="sm" variant="outline" onClick={() => setShowAllProcessing((prev) => !prev)}>
                        {showAllProcessing ? 'Show fewer' : `Show all (${sortedProcessingDocs.length})`}
                      </Button>
                    )}
                  </Flex>
                  <FileList
                    documents={displayedProcessingDocs}
                    onDeleteDocument={fetchDocuments}
                    showProgress={true}
                  />
                </Stack>
              ) : (
                <Text color="gray.500">No documents currently processing</Text>
              )}
            </TabPanel>

            <TabPanel px={{ base: 0, md: 2 }}>
              {sortedProcessedDocs.length > 0 ? (
                <Stack spacing={4}>
                  <Flex direction={{ base: 'column', md: 'row' }} justify="space-between" gap={3}>
                    <Text color="gray.600" fontSize="sm">
                      Showing {displayedProcessedDocs.length} of {sortedProcessedDocs.length} processed documents.
                    </Text>
                    {hasMoreProcessed && (
                      <Button size="sm" variant="outline" onClick={() => setShowAllProcessed((prev) => !prev)}>
                        {showAllProcessed ? 'Show fewer' : `Show all (${sortedProcessedDocs.length})`}
                      </Button>
                    )}
                  </Flex>
                  <FileList
                    documents={displayedProcessedDocs}
                    onDeleteDocument={fetchDocuments}
                    showProgress={false}
                  />
                </Stack>
              ) : (
                <Text color="gray.500">No processed documents yet</Text>
              )}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </Box>
    </Stack>
  );  
};  

export default Dashboard;