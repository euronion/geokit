from geokit._core.regionmask import *

def placeItemsInMask( mask, separation, extent=None, placementDiv=10, itemsAtEdge=True, asPoints=False, yAtTop=True):
    """Places items in a matrix mask with a minimal separation distance between 
    items

    * A maximum of one item can be placed somewhere in each mask pixel

    Inputs:
        extent - geokit.Extent
            * If an 'extent' is not given, the function will return the index 
              locations within the mask where an item can be placed
            * If an 'extent' is given, the function will compute the item locations 
              in relation to the given extent

        placementDiv - int
            * Increases the resolution of possibple item placements within each 
              mask pixel
            * Higher placementDiv means higher computation times

        itemsAtEdge - True/False
            * Determines whether or not items are allowed at the edge of acceptable 
              regions, or if there should be a buffer (separation/2) between each 
              item and an edge
            * Searching for the edge takes extra computation and is slower than when not searching for the edge

        asPoints - True/False
            * If True, returned value will be a list os OGR point objects

        yAtTop - True/False
            * Only factors in when and extent has been given
            * If True, the mask indexes are assumed to start at the top of the extent's y-dimension
    """

    # Get the useful sizes
    ySize = mask.shape[0]
    xSize = mask.shape[1]
    divXSize = (xSize*placementDiv)
    divYSize = (ySize*placementDiv)
    
    # compute index distance
    if extent is None:
        distance = separation
    else:
        dx = (extent.xMax-extent.xMin)/mask.shape[1]
        dy = (extent.yMax-extent.yMin)/mask.shape[0]

        if not isclose(dx,dy):
            raise GeoKitError("Computed pixelWidth does not match pixelHeight. Try a different Extent")

        distance = separation/dx

    width = int(np.round(placementDiv*distance))

    # Make stamp
    xx = np.arange(-width,width+1)
    yy = np.arange(-width,width+1)
    xx,yy = np.meshgrid(xx,yy)
    if itemsAtEdge:
        stamp = (xx*xx+yy*yy)>(width*width) # in this case, we want an 'inverse' stamp
    else:
        stamp = (xx*xx+yy*yy)<=(width/2*width/2)

    # Initialize a placement exclusion matrix
    itemExclusion = np.zeros((mask.shape[0]*placementDiv+2*width,mask.shape[1]*placementDiv+2*width), dtype='bool')
    itemExclusion[width:-width,width:-width] = scaleMatrix(mask, placementDiv)

    # Get the indexes which are in the suitability range
    yIndexes, xIndexes = np.where(mask > 0.5)

    # Cast indexes to divided indicies
    yDivStartIndexes = yIndexes*placementDiv+width
    xDivStartIndexes = xIndexes*placementDiv+width
    yDivEndIndexes = yDivStartIndexes + placementDiv + 1
    xDivEndIndexes = xDivStartIndexes + placementDiv + 1

    # Loop over potential placements
    divLocations = []
    for i in range(len(yIndexes)):
        # Get the extent of the current pixel in the DIVIDED matrix
        yDivStart = yDivStartIndexes[i]
        yDivEnd = yDivEndIndexes[i]
        xDivStart = xDivStartIndexes[i]
        xDivEnd = xDivEndIndexes[i]

        # Search for available locations
        yTmp, xTmp = np.where(itemExclusion[yDivStart:yDivEnd, xDivStart:xDivEnd]) # finds any points which are "True"
        if yTmp.size==0:continue
        
        # cast back to divided indicies
        potentialYDivLocs = yTmp+yDivStart
        potentialXDivLocs = xTmp+xDivStart

        # Try to locate a free spot
        yDivLoc = None
        xDivLoc = None

        if itemsAtEdge: # take the first free pixel, then stamp exclusion matrix
            yDivLoc = potentialYDivLocs[0]
            xDivLoc = potentialXDivLocs[0]

            currentArea = itemExclusion[yDivLoc-width:yDivLoc+width+1,xDivLoc-width:xDivLoc+width+1]
            itemExclusion[yDivLoc-width:yDivLoc+width+1,xDivLoc-width:xDivLoc+width+1] = np.logical_and(currentArea, stamp) # only keep those areas which remain after inverse stamping
        
        else: # Search for the first spot where the full stamp area is free, then set the item's location to False
            for yy, xx in zip(potentialYDivLocs, potentialXDivLocs):
                currentArea = itemExclusion[yy-width:yy+width+1,xx-width:xx+width+1]
                if not currentArea[stamp].all(): continue # skip if any point in the stamp is False

                # we should only get here if a suitable location was found
                yDivLoc = yy
                xDivLoc = xx
                itemExclusion[yDivLoc-width:yDivLoc+width+1,xDivLoc-width:xDivLoc+width+1][stamp] = False
                break

        # Save the found location
        if yDivLoc is None: continue

        divLocations.append( (xDivLoc, yDivLoc) )

    # Compute index locations
    if len(divLocations) == 0: return None
    indexLocations = (np.array(divLocations)-width)/placementDiv

    # Translate to extent domain, maybe
    if extent is None:
        finalLocations = indexLocations
    else:
        finalLocations = np.zeros(indexLocations.shape)

        finalLocations[:,0] = indexLocations[:,0]*dx + extent.xMin
        if yAtTop:
            finalLocations[:,1] = extent.yMax - indexLocations[:,1]*dy
        else:
            finalLocations[:,1] = extent.yMin + indexLocations[:,1]*dy

    # Transform into points, maybe
    if asPoints:
        srs = None if extent is None else extent.srs

        points = [makePoint( x,y, srs=srs ).Buffer(separation/2) for x,y in finalLocations]
        #points = [makePoint( x,y, srs=srs ) for x,y in finalLocations]

        return points
    else:
        return finalLocations
