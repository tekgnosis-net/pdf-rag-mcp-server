import React from 'react';  
import {
  Box,
  Button,
  Flex,
  Heading,
  HStack,
  IconButton,
  Menu,
  MenuButton,
  MenuItem,
  MenuList,
} from '@chakra-ui/react';  
import { Link as RouterLink } from 'react-router-dom';  
import { FiHome, FiBook, FiGithub, FiMenu, FiSearch } from 'react-icons/fi';  

const Header = () => {  
  return (  
    <Box bg="blue.700" color="white" px={4} py={3} shadow="md">  
      <Flex justify="space-between" align="center" maxW="container.xl" mx="auto">  
        <Flex align="center">  
          <Heading size="md" mr={2}>MCP PDF Knowledge Base</Heading>  
          <Menu isLazy> 
            <MenuButton
              as={IconButton}
              icon={<FiMenu />}
              variant="outline"
              display={{ base: 'inline-flex', md: 'none' }}
              aria-label="Open navigation"
              colorScheme="whiteAlpha"
              size="sm"
              ml={2}
            />
            <MenuList color="black">
              <MenuItem as={RouterLink} to="/" icon={<FiHome />}>
                Home
              </MenuItem>
              <MenuItem as={RouterLink} to="/search" icon={<FiSearch />}>
                Search
              </MenuItem>
              <MenuItem as={RouterLink} to="/settings" icon={<FiBook />}>
                Settings
              </MenuItem>
            </MenuList>
          </Menu>
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
              as={RouterLink}
              to="/search"
              variant="ghost"
              colorScheme="whiteAlpha"
              leftIcon={<FiSearch />}
              size="sm"
            >
              Search
            </Button>
            <Button
              as={RouterLink}
              to="/settings"
              variant="ghost"
              colorScheme="whiteAlpha"
              leftIcon={<FiBook />}
              size="sm"
            >
              Settings
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