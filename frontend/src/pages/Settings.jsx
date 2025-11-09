import React, { useEffect, useState } from 'react';
import {
  Box,
  Heading,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Input,
  Textarea,
  HStack,
  Text,
  useToast,
} from '@chakra-ui/react';
import axios from 'axios';

const Settings = () => {
  const [blacklist, setBlacklist] = useState([]);
  const [filename, setFilename] = useState('');
  const [reason, setReason] = useState('');
  const [reparseInput, setReparseInput] = useState('');
  const [isReparseAllLoading, setIsReparseAllLoading] = useState(false);
  const [isReparseSelectedLoading, setIsReparseSelectedLoading] = useState(false);
  const toast = useToast();

  const loadBlacklist = async () => {
    try {
      const resp = await axios.get('/api/blacklist');
      setBlacklist(resp.data || []);
    } catch (err) {
      console.error('Failed to load blacklist', err);
      toast({ title: 'Failed to load blacklist', status: 'error' });
    }
  };

  useEffect(() => {
    loadBlacklist();
  }, []);

  const handleAdd = async () => {
    if (!filename) return;
    try {
      const resp = await axios.post('/api/blacklist', { filename, reason });
      toast({ title: 'Blacklisted', description: `Added ${resp.data.filename}` });
      setFilename('');
      setReason('');
      loadBlacklist();
    } catch (err) {
      console.error('Add blacklist failed', err);
      toast({ title: 'Failed to add blacklist', status: 'error' });
    }
  };

  const handleRemove = async (id) => {
    try {
      await axios.delete(`/api/blacklist/${id}`);
      toast({ title: 'Un-blacklisted' });
      loadBlacklist();
    } catch (err) {
      console.error('Remove failed', err);
      toast({ title: 'Failed to remove', status: 'error' });
    }
  };

  const summarizeSkipped = (skipped = {}) => {
    const parts = Object.entries(skipped)
      .filter(([, items]) => Array.isArray(items) && items.length > 0)
      .map(([key, items]) => `${key}: ${items.length}`);
    return parts.join(', ');
  };

  const handleReparseAll = async () => {
    setIsReparseAllLoading(true);
    try {
      const resp = await axios.post('/api/reparse', { mode: 'all' });
      const { queued = [], skipped = {} } = resp.data || {};
      const summary = summarizeSkipped(skipped);
      toast({
        title: 'Reparse scheduled',
        description: `Queued ${queued.length} document(s).${summary ? ` Skipped -> ${summary}` : ''} Cleanup runs in the background; monitor progress from the Dashboard.`,
        status: 'success',
        duration: 6000,
      });
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to queue reparse';
      toast({ title: detail, status: 'error' });
    } finally {
      setIsReparseAllLoading(false);
    }
  };

  const handleReparseSelected = async () => {
    const parsed = (reparseInput.split(/[\n,]/) || [])
      .map((entry) => entry.trim())
      .filter((entry, index, arr) => entry && arr.indexOf(entry) === index);

    if (parsed.length === 0) {
      toast({ title: 'Provide at least one filename', status: 'warning' });
      return;
    }

    setIsReparseSelectedLoading(true);
    try {
      const resp = await axios.post('/api/reparse', { mode: 'selected', filenames: parsed });
      const { queued = [], skipped = {} } = resp.data || {};
      const summary = summarizeSkipped(skipped);
      toast({
        title: 'Reparse scheduled',
        description: `Queued ${queued.length} document(s).${summary ? ` Skipped -> ${summary}` : ''} Cleanup runs in the background; monitor progress from the Dashboard.`,
        status: 'success',
        duration: 6000,
      });
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Failed to queue selected reparse';
      toast({ title: detail, status: 'error' });
    } finally {
      setIsReparseSelectedLoading(false);
    }
  };

  return (
    <Box>
      <Heading size="md" mb={4}>Settings</Heading>

      <Box mb={6} p={4} bg="white" borderRadius="md" shadow="sm">
        <Heading size="sm" mb={3}>Reprocess Documents</Heading>
        <Text fontSize="sm" color="gray.600" mb={4}>
          Trigger a clean reparse to regenerate markdown pages and vectors. Use the bulk option to reset everything or provide specific filenames to target individual documents.
        </Text>
        <HStack spacing={3} mb={4} align="flex-start">
          <Button colorScheme="blue" onClick={handleReparseAll} isLoading={isReparseAllLoading}>
            Reprocess All PDFs
          </Button>
          <Box flex={1}>
            <Textarea
              placeholder="Enter exact filenames (one per line or separated by commas)"
              value={reparseInput}
              onChange={(e) => setReparseInput(e.target.value)}
              rows={4}
            />
            <HStack justify="flex-end" mt={2}>
              <Button onClick={handleReparseSelected} isLoading={isReparseSelectedLoading}>
                Reprocess Listed Files
              </Button>
            </HStack>
          </Box>
        </HStack>
        <Text fontSize="xs" color="gray.500">
          Tip: Partial matches like &quot;series-22&quot; may queue many PDFs. The cleanup now runs asynchronously—refresh the Dashboard or watch live updates over WebSocket.
        </Text>
      </Box>

      <Box mb={6} p={4} bg="white" borderRadius="md" shadow="sm">
        <Heading size="sm" mb={3}>Manage Blacklist</Heading>
        <HStack spacing={3} mb={3}>
          <Input placeholder="Filename to blacklist (exact match)" value={filename} onChange={(e) => setFilename(e.target.value)} />
          <Button onClick={handleAdd} colorScheme="red">Add</Button>
        </HStack>
        <Textarea placeholder="Optional reason" value={reason} onChange={(e) => setReason(e.target.value)} mb={3} />
      </Box>

      <Box p={4} bg="white" borderRadius="md" shadow="sm">
        <Heading size="sm" mb={3}>Blacklisted documents</Heading>
        <Table size="sm">
          <Thead>
            <Tr>
              <Th>Filename</Th>
              <Th>Reason</Th>
              <Th>Blacklisted At</Th>
              <Th>Actions</Th>
            </Tr>
          </Thead>
          <Tbody>
            {blacklist.map((d) => (
              <Tr key={d.id}>
                <Td>{d.filename}</Td>
                <Td>{d.blacklist_reason}</Td>
                <Td>{d.blacklisted_at ? new Date(d.blacklisted_at).toLocaleString() : ''}</Td>
                <Td>
                  <Button size="sm" onClick={() => handleRemove(d.id)}>Unblacklist</Button>
                </Td>
              </Tr>
            ))}
          </Tbody>
        </Table>
      </Box>
    </Box>
  );
};

export default Settings;
