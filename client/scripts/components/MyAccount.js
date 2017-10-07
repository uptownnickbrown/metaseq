import React from 'react';
import Firebase from 'firebase';
import axios from 'axios';
import apiConfig from '../config/api.js';
import { Link } from 'react-router';

// Material Design stuff
import RaisedButton from 'material-ui/RaisedButton';
import FlatButton from 'material-ui/FlatButton';
import MuiThemeProvider from 'material-ui/styles/MuiThemeProvider';
import ColorPalette from './ColorPalette';
import getMuiTheme from 'material-ui/styles/getMuiTheme';
import Paper from 'material-ui/Paper';
import {Table, TableBody, TableFooter, TableHeader, TableHeaderColumn, TableRow, TableRowColumn} from 'material-ui/Table';

import Header from './Header';

var apiRequest = axios.create({
  baseURL: apiConfig.baseURL
});

var MyAccount = React.createClass({
  getInitialState: function() {
      return {
        'firebase':{
          'uid':null,
          'name':null,
          'photo':null
        },
        'discoveries': []
      }
  },

  componentWillMount: function() {
    var user = Firebase.auth().currentUser;
    var self = this;
    if (user) {
      apiRequest.get("/user/"+user.uid+"/discoveries")
      .then(function (response) {
        self.setState({"discoveries": response.data.discoveries});
      });
      this.state.firebase.name = user.displayName;
      this.state.firebase.uid = user.uid;
      this.state.firebase.photo = user.photoURL;
      this.setState(this.state.firebase);
    }
  },

  triggerLogin : function() {
    var successfulLogin = this.successfulLogin;
    var provider = new Firebase.auth.GoogleAuthProvider();
    var auth = Firebase.auth().signInWithPopup(provider).then(function(result) {
      var user = result.user;
      successfulLogin(user);
    }).catch(function(error) {
      console.log("couldn't log in for some reason");
      console.log(error);
    });
  },

  triggerLogout : function() {
    var accountComponent = this;
    var auth = Firebase.auth().signOut().then(function() {
      accountComponent.state.firebase.name = null;
      accountComponent.state.firebase.uid = null;
      accountComponent.state.firebase.photo = null;
      accountComponent.setState(accountComponent.state.firebase);
    }, function(error) {
      console.log("couldn't log out for some reason");
      console.log(error);
    });
  },

  successfulLogin : function(user) {
    var self = this;
    self.state.firebase.name = user.displayName;
    self.state.firebase.uid = user.uid;
    self.state.firebase.photo = user.photoURL;
    apiRequest.post("/user/create", {
      "firebase_id":self.state.firebase.uid,
      "firebase_name":self.state.firebase.name,
      "admin":0
    }).then(function(response){
      console.log(response);
      self.setState({"firebase": self.state.firebase});
    });

    apiRequest.get("/user/"+user.uid+"/discoveries")
    .then(function (response) {
      self.setState({"discoveries": response.data.discoveries});
    });

    this.setState(this.state.firebase);

  },

  render : function() {
    if (!this.state.firebase.uid) return (
      <div>
        <Header history={this.props.history}/>
        <MuiThemeProvider muiTheme={getMuiTheme(ColorPalette)}>
          <Paper className="myacct-loggedout" >
            <h3>Log in with Google to view your MetaSeek account.</h3>
            <div className="login-buttons">
              <RaisedButton
                label="Log In"
                onClick={this.triggerLogin}
                primary={true}
                disabled={this.state.firebase.uid}
              />
            </div>
          </Paper>
        </MuiThemeProvider>
      </div>
    );

    var tableHeaderStyles = {color:'#fff',fontFamily:'Roboto',fontSize:'20px',fontWeight:600};

    return (
      <div>
        <Header history={this.props.history}/>
        <MuiThemeProvider muiTheme={getMuiTheme(ColorPalette)}>
          <div>
            <Paper className="myacct-loggedin" >
              <div>
                 <img className="profile-image-myacct" src={this.state.firebase.photo}/>
              </div>
              <div className="myacct-user">
                <h2 className="myacct-name">{this.state.firebase.name}</h2>
                <div className="myacct-logout-button">
                  <FlatButton
                    label="Log Out"
                    onClick={this.triggerLogout}
                    primary={true}
                  />
                </div>
              </div>
              <div className="num-discoveries">
                <span className="discovery-header-user">{this.state.discoveries.length + " saved discoveries"}</span>
              </div>
            </Paper>

            <Paper className="user-discoveries-table">
              <Table bodyStyle={{overflowX: 'scroll', width:'100%' }} fixedHeader={false} fixedFooter={false} selectable={false} style={{'tableLayout':'auto'}}>
                <TableHeader style={{backgroundColor:'#979CF2'}} adjustForCheckbox={false} displaySelectAll={false} enableSelectAll={false}>
                  <TableRow selectable={false}>
                    <TableHeaderColumn style={tableHeaderStyles}>{this.state.discoveries.length + " Discoveries"}</TableHeaderColumn>
                    <TableHeaderColumn style={tableHeaderStyles}>Date Created</TableHeaderColumn>
                    <TableHeaderColumn style={tableHeaderStyles}></TableHeaderColumn>
                  </TableRow>
                </TableHeader>
                <TableBody showRowHover={false} stripedRows={false} displayRowCheckbox={false} preScanRows={false}>
                  {this.state.discoveries.map( (discovery, index) => (
                    <TableRow selectable={false} key={index}>
                      <TableRowColumn style={{fontSize: "18px", width: "85%"}} >{discovery.discovery_title}</TableRowColumn>
                      <TableRowColumn>{discovery.timestamp.substr(5, 20)}</TableRowColumn>
                      <TableRowColumn style={{textAlign: "center"}}>
                        <Link to={discovery.uri}>
                        <RaisedButton label={"discovery details"} secondary={true} />
                        </Link>
                      </TableRowColumn>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>

          </div>
        </MuiThemeProvider>
      </div>
    )
  }
});

export default MyAccount;
