import React from 'react';
import axios from 'axios';
import apiConfig from '../config/api.js';

import AddDatasetForm from './AddDatasetForm';
import Header from './Header';

var apiRequest = axios.create({
  baseURL: apiConfig.baseURL
});

var AddDataset = React.createClass({
    getInitialState: function() {
        return {}
    },

    addDataset : function(dataset) {
      var self = this;
      console.log('Manually uploading datasets currently disabled.');
      //apiRequest.post('/dataset/create', dataset)
      //.then(function (response) {
      //  self.props.history.push('/dataset/' + response.data.dataset.id);
      //});
    },
    render: function() {
        return (
          <div>
            <Header history={this.props.history}/>
            <div>
              <h2>Contribute a dataset</h2>
              <AddDatasetForm addDataset={this.addDataset}/>
            </div>
          </div>
        )
    }
});

export default AddDataset;
