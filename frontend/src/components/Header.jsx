import React from 'react';  
import { Box, Flex, Heading, Button, HStack, Text, Icon } from '@chakra-ui/react';  
import { Link as RouterLink } from 'react-router-dom';  
import { FiHome, FiBook, FiGithub } from 'react-icons/fi';  

const Header = () => {  
  return (  
    <Box bg="blue.700" color="white" px={4} py={3} shadow="md">  
      <Flex justify="space-between" align="center" maxW="container.xl" mx="auto">  
        <Flex align="center">  
          <Heading size="md" mr={2}>MCP PDF Knowledge Base</Heading>  
          <HStack spacing={3} ml={8} display={{ base: 'none', md: 'flex' }}>  
            <Button  
              as={RouterLink}  
              to="/"  
              variant="ghost"  
              colorScheme="whiteAlpha"  
              leftIcon={<FiHome />}  
              size="sm"  
            >  
              Home  
            </Button>  
            <Button  
              as="a"  
              href="https://cursor.sh"  
              target="_blank"   
              variant="ghost"  
              colorScheme="whiteAlpha"  
              leftIcon={<FiBook />}  
              size="sm"  
            >  
              Cursor Docs  
            </Button>  
          </HStack>  
        </Flex>  
        
        <Button  
          as="a"  
          href="https://github.com/tekgnosis-net/pdf-rag-mcp-server"  
          target="_blank"   
          leftIcon={<FiGithub />}  
          variant="outline"  
          colorScheme="whiteAlpha"  
          size="sm"  
        >  
          View on GitHub  
        </Button>  
      </Flex>  
    </Box>  
  );  
};  

export default Header;